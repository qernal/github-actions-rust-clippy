FROM python:3.9-alpine
LABEL org.opencontainers.image.source https://github.com/qernal/github-actions-rust-clippy

# add packages
RUN apk add curl rust openssl-dev --no-cache
RUN curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs --output /tmp/rustup.sh && chmod +x /tmp/rustup.sh && /tmp/rustup.sh -y
RUN ln -s $HOME/.cargo/bin/cargo /usr/bin/cargo
COPY ./src /

# setup src
RUN mkdir /app
COPY ./ ./app/

CMD ["python", "/clippy.py"]