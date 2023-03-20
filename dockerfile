FROM python:3.6-slim

RUN sed -i "s/http/https/g" /etc/apt/sources.list
RUN sed -i "s/deb.debian.org/mirrors.aliyun.com/g" /etc/apt/sources.list
RUN sed -i "s/security.debian.org\/debian-security/mirrors.aliyun.com\/debian-security/g" /etc/apt/sources.list
RUN apt-get update
RUN apt-get install -y --no-install-recommends build-essential gcc wget
RUN apt-get install -y supervisor
RUN apt-get install telnet
RUN apt-get install -y python3-dev
WORKDIR /backtrader


RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
ENV TA_LIBRARY_PATH="/opt/venv/lib"
ENV TA_INCLUDE_PATH="/opt/venv/include"

RUN pip install --upgrade pip -i https://mirrors.aliyun.com/pypi/simple/

RUN pip install numpy -i https://mirrors.aliyun.com/pypi/simple/

RUN wget http://prdownloads.sourceforge.net/ta-lib/ta-lib-0.4.0-src.tar.gz && \
    tar -zxvf ta-lib-0.4.0-src.tar.gz && \
    cd ta-lib/ && \
    ./configure --prefix=/opt/venv && \
    make && \
    make install

RUN pip install --global-option=build_ext --global-option="-L/opt/venv/lib" TA-Lib==0.4.16 -i https://mirrors.aliyun.com/pypi/simple/

RUN rm -R ta-lib ta-lib-0.4.0-src.tar.gz

COPY requirements.txt /backtrader/requirements.txt

RUN pip install -r /backtrader/requirements.txt -i https://mirrors.aliyun.com/pypi/simple/ 

COPY ./BacktraderStrats /backtrader/BacktraderStrats
RUN mkdir -p /backtrader/BacktraderStrats/logs
ENV PATH="/opt/venv/bin:$PATH"
ENV LD_LIBRARY_PATH="/opt/venv/lib"


RUN wget https://softwarefile.futunn.com/FutuOpenD_7.1.3308_NN_Ubuntu16.04.tar.gz && \
    tar -zxvf FutuOpenD_7.1.3308_NN_Ubuntu16.04.tar.gz && \
    mv /backtrader/FutuOpenD_7.1.3308_NN_Ubuntu16.04/FutuOpenD_7.1.3308_NN_Ubuntu16.04 /backtrader/FutuOpenD 

RUN rm -R FutuOpenD_7.1.3308_NN_Ubuntu16.04.tar.gz
RUN rm -R /backtrader/FutuOpenD_7.1.3308_NN_Ubuntu16.04 
RUN rm -R /backtrader/FutuOpenD/FutuOpenD.xml 
COPY FutuOpenD.xml /backtrader/FutuOpenD/FutuOpenD.xml
COPY futusupervisord.conf /etc/supervisor/conf.d/futusupervisord.conf
RUN mkdir -p /var/log/supervisor
RUN mkdir -p /backtrader/futu/log 
CMD ["/usr/bin/supervisord"]