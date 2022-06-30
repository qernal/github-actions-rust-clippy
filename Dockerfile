FROM clux/muslrust:1.61.0-stable
LABEL org.opencontainers.image.source https://github.com/qernal/github-actions-rust-clippy

# add packages
RUN apt-get update && apt-get install -y \
  python3 &&\
  rm -rf /var/lib/apt/lists/*

# add clippy into rustup
RUN rustup component add clippy

# add clippy python app
COPY ./src /
RUN mkdir -p /root/.ssh
RUN mkdir /app
COPY ./ ./app/

# into app
CMD ["python3", "/clippy.py"]