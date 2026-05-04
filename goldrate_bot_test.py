import datetime
today = datetime.date.today()
import sys
sys.stdout.reconfigure(encoding='utf-8')

from selenium import webdriver
from selenium.webdriver.common.by import By
import pywhatkit

browser = webdriver.Chrome()
browser.get("https://www.goodreturns.in/gold-rates/nagpur.html")
title = browser.title.split(',')[0]

gold24 = browser.find_element(By.ID, "24K-price")
gold22 = browser.find_element(By.ID, "22K-price")
gold18 = browser.find_element(By.ID, "18K-price")

message = f"""💰 {title} - {today.strftime("%b %d, %Y")}
- 24K: {gold24.text}
- 22K: {gold22.text}
- 18K: {gold18.text}"""

print(message)

browser.quit()

pywhatkit.sendwhatmsg_instantly("+918149334152", message, wait_time=10, tab_close=True)