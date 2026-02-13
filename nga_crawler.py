name: NGA新回复推送（精简版）
on:
  workflow_dispatch:  # 支持手动触发
  schedule:
    - cron: '*/5 * * * *'  # 每5分钟执行一次（UTC时间，对应北京时间+8）

jobs:
  crawl_nga:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Set timezone to Asia/Shanghai
        run: |
          sudo timedatectl set-timezone Asia/Shanghai
          date  # 打印当前时间，验证时区是否生效

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.10'  # 指定Python版本，避免兼容性问题

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install requests beautifulsoup4 pytz  # 安装脚本依赖

      - name: Run NGA crawler
        env:
          # 从GitHub Secrets读取敏感配置，避免硬编码
          NGA_COOKIE: ${{ secrets.NGA_COOKIE }}
          SERVERCHAN_SENDKEY: ${{ secrets.SERVERCHAN_SENDKEY }}
        run: |
          python nga_crawler.py  # 执行核心监控脚本
