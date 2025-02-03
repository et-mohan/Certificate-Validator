#!/usr/bin/env bash
# Install Tesseract OCR
wget https://github.com/tesseract-ocr/tesseract/archive/refs/tags/4.1.1.tar.gz
tar -zxvf 4.1.1.tar.gz
cd tesseract-4.1.1
./autogen.sh
./configure
make
make install
ldconfig
cd ..
rm -rf tesseract-4.1.1 4.1.1.tar.gz
