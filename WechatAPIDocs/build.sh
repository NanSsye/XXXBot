#!/bin/bash
cd "$(dirname "$0")" || exit
make clean
make html

rm -rf ../docs/WechatAPIClient/*
cp -r _build/html/* ../docs/WechatAPIClient || exit