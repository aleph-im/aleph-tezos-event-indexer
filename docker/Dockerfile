# Specify the base image with the desired Python version
FROM --platform=linux/amd64 python:3.10.11-buster

# Set the DEBIAN_FRONTEND environment variable to noninteractive
RUN DEBIAN_FRONTEND=noninteractive

# Update the package lists in the package manager
RUN apt-get update

# Upgrade all installed packages to their latest versions
RUN apt-get upgrade -y

# Install required system dependencies using apt-get
RUN apt-get install gcc g++ make libsodium-dev libsecp256k1-dev libgmp-dev -y

# Create a new user named 'user' with /bin/bash as the default shell
RUN useradd -ms /bin/bash user

# Set the user context to 'user'
USER user

# Set the working directory to /home/user
WORKDIR /home/user

# Upgrade pip to version 23.1.2
RUN pip install --upgrade pip==23.1.2

# Copy the contents of the current directory to the /home/user directory in the container
COPY ../ .

# Install the Python dependencies listed in requirements.txt
RUN pip install -r requirements.txt

# Specify the default command to run when the container starts
CMD ["python", "run.py"]