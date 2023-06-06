FROM --platform=linux/amd64 python:3.11.3-slim

RUN DEBIAN_FRONTEND=noninteractive
RUN apt-get update
RUN apt-get upgrade -y
# RUN apt-get install gcc g++ make libsodium-dev libsecp256k1-dev libgmp-dev -y

RUN useradd -ms /bin/bash user
USER user

WORKDIR /home/user
RUN pip install --upgrade pip==23.1.2

COPY ../ .
RUN pip install -r requirements.txt

CMD ["python", "run.py"]