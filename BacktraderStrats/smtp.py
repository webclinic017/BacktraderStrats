import smtplib
import configparser
import logging

from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.image import MIMEImage
from email.utils import formataddr
from email.header import Header

from logging.config import fileConfig

fileConfig('logging.conf')
logger = logging.getLogger()

mail_conf = 'mail.conf'
cf = configparser.ConfigParser()
cf.read(mail_conf)

smtp_srv = cf['SMTP']['SmtpServer']
smtp_port = cf['SMTP']['SmtpPort']
smtp_account = cf['SMTP']['SmtpAccount']
smtp_pwd = cf['SMTP']['SmtpPassword']


sender = cf['MAIL']['Sender']
from_name = cf['MAIL']['SenderName']
receiver = cf['MAIL']['Receiver']
receivers = [receiver]



def send_mail(msg_text, subject):
    msg = MIMEText(msg_text, 'plain', 'utf-8')
    msg['From'] = formataddr([from_name, sender])
    msg['Subject'] = Header(subject, 'utf-8')

    try:
        srv = smtplib.SMTP_SSL(smtp_srv.encode(), smtp_port)
        srv.login(smtp_account, smtp_pwd)
        srv.sendmail(sender, receivers, msg.as_string())
    except Exception as ex:
        logger.error('send mail failed...')
        logger.error(ex)
    finally:
        srv.quit()
    

