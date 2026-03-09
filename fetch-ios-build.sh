#!/bin/bash
# 从 GitHub 下载最新 iOS 构建到下载目录
cd "$(dirname "$0")"
URL=$(curl -s "https://api.github.com/repos/alexwang-2021/baoshui/releases/latest" | grep "browser_download_url.*App-simulator" | cut -d'"' -f4)
if [ -n "$URL" ]; then
  curl -sL -o App-simulator.zip "$URL"
  echo "已下载到 $(pwd)/App-simulator.zip"
else
  echo "暂无 Release，请先在 GitHub Actions 完成构建"
fi
