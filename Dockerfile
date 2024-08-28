FROM apache/airflow:2.5.1-python3.10

USER root

RUN apt-get update \
  && apt-get install -y --no-install-recommends \
    vim \
    wget \
    gnupg \
    apt-transport-https \
    ca-certificates \
    curl \
    unzip \ 
  && apt-get autoremove -yqq --purge \
  && apt-get clean \
  && apt --fix-broken install \
  && rm -rf /var/lib/apt/lists/*

# WORKDIR /usr/src
WORKDIR /opt/airflow
RUN apt-get -y update
RUN sudo apt-get -f install
RUN apt install -y wget unzip
RUN wget https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
RUN sudo apt-get install -y ./google-chrome-stable_current_amd64.deb


RUN apt-get install wget
RUN apt-get install -yqq unzip
RUN wget -O /tmp/chromedriver.zip https://edgedl.me.gvt1.com/edgedl/chrome/chrome-for-testing/116.0.5845.96/linux64/chromedriver-linux64.zip
RUN mkdir chrome
# RUN unzip /tmp/chromedriver.zip chromedriver-linux64/chromedriver -d /usr/src/chrome
RUN unzip /tmp/chromedriver.zip chromedriver-linux64/chromedriver -d /opt/airflow/chrome


USER airflow

COPY ./dags /opt/airflow/dags

RUN pip install --upgrade pip
COPY requirements.txt ./requirements.txt
RUN pip3 install -r requirements.txt
RUN pip install git+https://github.com/SKTBrain/KoBERT.git#egg=kobert_tokenizer&subdirectory=kobert_hf
RUN pip install --upgrade webdriver_manager

RUN airflow db init

CMD ["bash", "-c", "airflow webserver -p 8080 -D && airflow scheduler"]
