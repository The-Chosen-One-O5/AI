FROM python:3.10-slim

# Install FFmpeg and build tools for compiling tgcalls
RUN apt-get update && apt-get install -y \
    ffmpeg \
    gcc \
    g++ \
    make \
    git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .

# Install pytgcalls from GitHub (this will compile and install tgcalls automatically)
RUN pip install --no-cache-dir git+https://github.com/pytgcalls/pytgcalls.git

# Install all other requirements
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8080

# Run Flask keep_alive in background and main bot
CMD python keep_alive.py & python main.py
