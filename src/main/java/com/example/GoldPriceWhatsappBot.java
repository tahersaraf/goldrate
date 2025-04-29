package com.example;

import org.openqa.selenium.By;
import org.openqa.selenium.Keys;
import org.openqa.selenium.WebDriver;
import org.openqa.selenium.WebElement;
import org.openqa.selenium.chrome.ChromeDriver;
import org.openqa.selenium.chrome.ChromeOptions;
import org.openqa.selenium.support.ui.ExpectedConditions;
import org.openqa.selenium.support.ui.WebDriverWait;

import java.util.List;
import java.util.Arrays;
import java.time.Duration;
import java.time.LocalDate;
import java.time.format.DateTimeFormatter;

public class GoldPriceWhatsappBot {

    static WebDriver driver;
    static WebDriverWait wait;

    public static void main(String[] args) {
        setupDriver();

        try {
            String[] prices = scrapeGoldPrices();
            String goldMessage = formatGoldMessage(prices);

            // List of contacts to send the message to
            List<String> contacts = Arrays.asList(
                    "Taher Saraf"
                    // Add more contacts here as needed
            );

            // Send message to each contact
            for (String contact : contacts) {
                try {
                    System.out.println("Sending message to: " + contact);
                    sendWhatsappMessage(contact, goldMessage);
                    System.out.println("✅ Message sent to: " + contact);

                    // Short pause between sending messages
                    Thread.sleep(2000);
                } catch (Exception e) {
                    System.err.println("❌ Failed to send message to: " + contact);
                    System.err.println("Error: " + e.getMessage());
                }
            }

            System.out.println("✅ Gold prices sent to all contacts!");


            System.out.println("Waiting 5 seconds before closing browser...");
            Thread.sleep(5000);

        } catch (Exception e) {
            System.err.println("Error occurred: " + e.getMessage());
            e.printStackTrace();
        } finally {

            driver.quit();
        }
    }

    private static void setupDriver() {
        System.setProperty("webdriver.chrome.driver", "C:\\Users\\taher\\Documents\\chromedriver-win64\\chromedriver.exe");

        ChromeOptions options = new ChromeOptions();


        // Important for WhatsApp Web - keep session alive
        options.addArguments("--user-data-dir=C:\\Users\\taher\\Documents\\chrome-user-data");
        options.addArguments("--profile-directory=Default");

        driver = new ChromeDriver(options);
        wait = new WebDriverWait(driver, Duration.ofSeconds(30));
    }

    private static String[] scrapeGoldPrices() {
        driver.get("https://www.goodreturns.in/gold-rates/nagpur.html");


        wait.until(ExpectedConditions.presenceOfElementLocated(By.cssSelector(".gold-each-container")));

        List<WebElement> goldContainers = driver.findElements(By.cssSelector(".gold-each-container"));

        String price22k = "";
        String price24k = "";
        String price18k = "";

        for (WebElement container : goldContainers) {
            String title = container.findElement(By.cssSelector(".gold-top .gold-common-head")).getText();
            String price = container.findElement(By.cssSelector(".gold-bottom .gold-common-head")).getText();

            if (title.contains("22K")) {
                price22k = price;
            } else if (title.contains("24K")) {
                price24k = price;
            } else if (title.contains("18K")) {
                price18k = price;
            }
        }

        return new String[]{price24k, price22k, price18k};
    }

    private static String formatGoldMessage(String[] prices) {
        String today = LocalDate.now().format(DateTimeFormatter.ofPattern("dd MMM yyyy"));

        return "Gold Price Update for " + today + ":\n\n" +
                "24K: " + prices[0] + " /g\n" +
                "22K: " + prices[1] + " /g\n" +
                "18K: " + prices[2] + " /g\n";
    }

    private static void sendWhatsappMessage(String contactName, String message) {
        driver.get("https://web.whatsapp.com/");
        System.out.println("Please scan QR code if needed...");

        // Looking for the search box
        By searchBoxLocator = By.xpath("//div[@contenteditable='true'][@data-tab='3']");
        wait.until(ExpectedConditions.presenceOfElementLocated(searchBoxLocator));

        // Search for contact
        WebElement searchBox = driver.findElement(searchBoxLocator);
        searchBox.sendKeys(contactName);

        // Wait for search results to appear
        By contactResultLocator = By.xpath("//span[@title='" + contactName + "']");
        wait.until(ExpectedConditions.elementToBeClickable(contactResultLocator));

        // Click on the contact
        driver.findElement(contactResultLocator).click();

        // Wait for chat to load and message box to be available
        By messageBoxLocator = By.xpath("//div[@contenteditable='true'][@data-tab='10']");
        wait.until(ExpectedConditions.elementToBeClickable(messageBoxLocator));

        // Find message box and send message
        WebElement messageBox = driver.findElement(messageBoxLocator);



        for (char c : message.toCharArray()) {
            if (c == '\n') {
                // Use Shift+Enter for newlines within the same message
                messageBox.sendKeys(Keys.chord(Keys.SHIFT, Keys.ENTER));
            } else {
                messageBox.sendKeys(String.valueOf(c));
            }
        }


        messageBox.sendKeys(Keys.ENTER);

        // Wait for message to be sent
        try {
            wait.until(ExpectedConditions.presenceOfElementLocated(
                    By.cssSelector("span[data-icon='msg-check']")));
        } catch (Exception e) {
            System.out.println("Warning: Couldn't confirm message delivery, but message was sent");
        }
    }
}