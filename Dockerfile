FROM ubuntu:jammy

# Set environment variables to prevent interactive prompts during package installation
ENV DEBIAN_FRONTEND=noninteractive

# Set the working directory inside the container
WORKDIR /app

# Install additional dependencies if needed
RUN apt-get update && apt-get install -y \
    python3-pip \
    python3.10 \
    glpk-utils \
    libglpk-dev \
    glpk-doc \
    python3-swiglpk \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Copy your application code to the container
COPY requirements.txt /app

# Install required Python packages
RUN pip install --no-cache-dir -r requirements.txt

# Set the default command to run your application
CMD ["marimo", "edit", "project.py", "-p", "2718", "--host", "0.0.0.0"]