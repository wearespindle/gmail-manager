FROM ubuntu:14.04
MAINTAINER GMailManager

RUN apt-get update && apt-get install -y \
    python2.7-dev \
    python-pip \
    postgresql \
    postgresql-server-dev-9.3

RUN useradd docker
RUN echo "ALL ALL = (ALL) NOPASSWD: ALL" >> /etc/sudoers
WORKDIR /home/docker
ENV HOME /home/docker

ADD requirements.txt $HOME/requirements.txt
RUN pip install -r $HOME/requirements.txt

# Switch to docker user.
RUN chown -R docker:docker $HOME/
USER docker

# Install PuDB.
# PuDB does some weird folder creating stuff, leaving it unable to read with no apparent reason.
RUN mkdir -p $HOME/.config/pudb
RUN sudo pip install pudb
RUN sudo chown -R docker:docker $HOME/

ENV DEBUG 1
ENV SECRET_KEY abcdefghijklmnopqrstuvwxyz0123456789abcdefghijklmn
ENV DATABASE_URL postgres://gmailmanager:@db/gmailmanager

WORKDIR /home/docker/gmailmanager
