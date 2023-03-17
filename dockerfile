FROM python:3.6-slim

RUN apt-get update
RUN apt-get install -y --no-install-recommends build-essential gcc wget
RUN apt-get install -y supervisor
RUN apt-get install telnet
WORKDIR /backtrader


RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"


RUN pip install --upgrade pip

RUN pip install numpy

RUN wget http://prdownloads.sourceforge.net/ta-lib/ta-lib-0.4.0-src.tar.gz && \
    tar -zxvf ta-lib-0.4.0-src.tar.gz && \
    cd ta-lib/ && \
    ./configure --prefix=/opt/venv && \
    make && \
    make install

RUN pip install --global-option=build_ext --global-option="-L/opt/venv/lib" TA-Lib==0.4.16
RUN rm -R ta-lib ta-lib-0.4.0-src.tar.gz

COPY requirements.txt /backtrader/requirements.txt

RUN pip install -r /backtrader/requirements.txt 

COPY ./BacktraderStrats /backtrader/BacktraderStrats

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