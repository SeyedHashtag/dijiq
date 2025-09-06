#!/bin/bash

set -e

echo "Updating package list..."
sudo apt-get update -y

if ! command -v mongod &> /dev/null
then
    echo "MongoDB not found. Installing from official repository..."

    echo "Installing prerequisites..."
    sudo apt-get install -y gnupg curl

    echo "Importing the MongoDB public GPG key..."
    curl -fsSL https://www.mongodb.org/static/pgp/server-7.0.asc | \
    sudo gpg -o /usr/share/keyrings/mongodb-server-7.0.gpg --dearmor

    echo "Creating a list file for MongoDB..."
    echo "deb [ arch=amd64,arm64 signed-by=/usr/share/keyrings/mongodb-server-7.0.gpg ] https://repo.mongodb.org/apt/debian bookworm/mongodb-org/7.0 main" | \
    sudo tee /etc/apt/sources.list.d/mongodb-org-7.0.list

    echo "Reloading local package database..."
    sudo apt-get update -y

    echo "Installing the MongoDB packages..."
    sudo apt-get install -y mongodb-org
else
    echo "MongoDB is already installed."
fi

echo "Starting and enabling MongoDB service..."
sudo systemctl start mongod
sudo systemctl enable mongod

echo "Installing pymongo for Python..."
if python3 -m pip --version &> /dev/null; then
    python3 -m pip install pymongo
elif pip --version &> /dev/null; then
    pip install pymongo
else
    echo "pip is not installed. Please install python3-pip"
    exit 1
fi

# echo "Installing MongoDB driver for Go..."
# if command -v go &> /dev/null
# then
#     go get go.mongodb.org/mongo-driver/mongo
# else
#     echo "Go is not installed. Skipping Go driver installation."
# fi

echo "Database setup is complete."