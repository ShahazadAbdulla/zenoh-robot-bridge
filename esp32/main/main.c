#include <stdio.h>
#include <string.h>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "esp_log.h"
#include "esp_wifi.h"
#include "esp_event.h"
#include "nvs_flash.h"
#include "driver/ledc.h"
#include "zenoh-pico.h"

#define WIFI_SSID CONFIG_EXAMPLE_WIFI_SSID
#define WIFI_PASS CONFIG_EXAMPLE_WIFI_PASSWORD
#define TAG "ZENOH_ROBOT"

// --- TB6612FNG PINOUT ---
#define AIN1 4
#define AIN2 18
#define PWMA 19
#define BIN1 25
#define BIN2 26
#define PWMB 27
#define STBY 5

// --- LEDC CONFIG ---
#define LEDC_TIMER LEDC_TIMER_0
#define LEDC_MODE LEDC_LOW_SPEED_MODE
#define LEDC_FREQ 5000
#define LEDC_RES LEDC_TIMER_8_BIT

static EventGroupHandle_t s_wifi_event_group;
#define WIFI_CONNECTED_BIT BIT0

// --- MOTOR FUNCTIONS ---
static void motor_init(void)
{
    gpio_config_t io_conf = {
        .mode = GPIO_MODE_OUTPUT,
        .pin_bit_mask = (1ULL << AIN1) | (1ULL << AIN2) | 
                       (1ULL << BIN1) | (1ULL << BIN2) | (1ULL << STBY),
    };
    gpio_config(&io_conf);

    ledc_timer_config_t timer = {
        .speed_mode = LEDC_MODE,
        .timer_num = LEDC_TIMER,
        .duty_resolution = LEDC_RES,
        .freq_hz = LEDC_FREQ,
        .clk_cfg = LEDC_AUTO_CLK
    };
    ledc_timer_config(&timer);

    ledc_channel_config_t chA = {
        .gpio_num = PWMA,
        .speed_mode = LEDC_MODE,
        .channel = LEDC_CHANNEL_0,
        .timer_sel = LEDC_TIMER,
        .duty = 0,
        .hpoint = 0
    };
    ledc_channel_config(&chA);

    ledc_channel_config_t chB = {
        .gpio_num = PWMB,
        .speed_mode = LEDC_MODE,
        .channel = LEDC_CHANNEL_1,
        .timer_sel = LEDC_TIMER,
        .duty = 0,
        .hpoint = 0
    };
    ledc_channel_config(&chB);

    gpio_set_level(STBY, 1);
}

static void move(int16_t leftSpeed, int16_t rightSpeed)
{
    // Motor A (Left)
    if (leftSpeed > 0) {
        gpio_set_level(AIN1, 1); gpio_set_level(AIN2, 0);
    } else if (leftSpeed < 0) {
        gpio_set_level(AIN1, 0); gpio_set_level(AIN2, 1);
    } else {
        gpio_set_level(AIN1, 0); gpio_set_level(AIN2, 0);
    }
    ledc_set_duty(LEDC_MODE, LEDC_CHANNEL_0, abs(leftSpeed));
    ledc_update_duty(LEDC_MODE, LEDC_CHANNEL_0);

    // Motor B (Right)
    if (rightSpeed > 0) {
        gpio_set_level(BIN1, 1); gpio_set_level(BIN2, 0);
    } else if (rightSpeed < 0) {
        gpio_set_level(BIN1, 0); gpio_set_level(BIN2, 1);
    } else {
        gpio_set_level(BIN1, 0); gpio_set_level(BIN2, 0);
    }
    ledc_set_duty(LEDC_MODE, LEDC_CHANNEL_1, abs(rightSpeed));
    ledc_update_duty(LEDC_MODE, LEDC_CHANNEL_1);
}

static void stop_motors(void)
{
    ledc_set_duty(LEDC_MODE, LEDC_CHANNEL_0, 0);
    ledc_update_duty(LEDC_MODE, LEDC_CHANNEL_0);
    ledc_set_duty(LEDC_MODE, LEDC_CHANNEL_1, 0);
    ledc_update_duty(LEDC_MODE, LEDC_CHANNEL_1);
    gpio_set_level(STBY, 0);
}

// --- WIFI ---
static void event_handler(void* arg, esp_event_base_t event_base,
                          int32_t event_id, void* event_data)
{
    if (event_base == WIFI_EVENT && event_id == WIFI_EVENT_STA_DISCONNECTED) {
        ESP_LOGW(TAG, "WiFi disconnected, retrying...");
        esp_wifi_connect();
    } else if (event_base == IP_EVENT && event_id == IP_EVENT_STA_GOT_IP) {
        ip_event_got_ip_t* event = (ip_event_got_ip_t*) event_data;
        ESP_LOGI(TAG, "Got IP: " IPSTR, IP2STR(&event->ip_info.ip));
        xEventGroupSetBits(s_wifi_event_group, WIFI_CONNECTED_BIT);
    }
}

static void wifi_init_sta(void)
{
    s_wifi_event_group = xEventGroupCreate();
    ESP_ERROR_CHECK(esp_netif_init());
    ESP_ERROR_CHECK(esp_event_loop_create_default());
    esp_netif_create_default_wifi_sta();

    wifi_init_config_t cfg = WIFI_INIT_CONFIG_DEFAULT();
    ESP_ERROR_CHECK(esp_wifi_init(&cfg));

    esp_event_handler_instance_t instance_any_id;
    esp_event_handler_instance_t instance_got_ip;
    ESP_ERROR_CHECK(esp_event_handler_instance_register(WIFI_EVENT,
                                                        ESP_EVENT_ANY_ID,
                                                        &event_handler,
                                                        NULL,
                                                        &instance_any_id));
    ESP_ERROR_CHECK(esp_event_handler_instance_register(IP_EVENT,
                                                        IP_EVENT_STA_GOT_IP,
                                                        &event_handler,
                                                        NULL,
                                                        &instance_got_ip));

    wifi_config_t wifi_config = {
        .sta = {
            .ssid = WIFI_SSID,
            .password = WIFI_PASS,
            .threshold.authmode = WIFI_AUTH_WPA2_PSK,
        },
    };
    ESP_ERROR_CHECK(esp_wifi_set_mode(WIFI_MODE_STA));
    ESP_ERROR_CHECK(esp_wifi_set_config(WIFI_IF_STA, &wifi_config));
    ESP_ERROR_CHECK(esp_wifi_start());
    ESP_ERROR_CHECK(esp_wifi_connect());

    ESP_LOGI(TAG, "Waiting for WiFi IP...");
    xEventGroupWaitBits(s_wifi_event_group, WIFI_CONNECTED_BIT,
                        pdFALSE, pdTRUE, portMAX_DELAY);
    ESP_LOGI(TAG, "WiFi ready");
}

// --- ZENOH CALLBACK ---
static void data_handler(z_loaned_sample_t *sample, void *arg)
{
    z_view_string_t keystr;
    z_keyexpr_as_view_string(z_sample_keyexpr(sample), &keystr);

    z_owned_slice_t payload;
    z_bytes_to_slice(z_sample_payload(sample), &payload);

    if (z_slice_len(z_loan(payload)) == 2) {
        // Parse signed bytes: [-128, 127] for direction + speed
        int16_t left = (int8_t)z_slice_data(z_loan(payload))[0];
        int16_t right = (int8_t)z_slice_data(z_loan(payload))[1];
        
        // Scale to 8-bit PWM: map [-127,127] → [-255,255]
        left = (left * 255) / 127;
        right = (right * 255) / 127;
        
        move(left, right);
        ESP_LOGI(TAG, "Drive: L=%d R=%d", left, right);
    } else {
        ESP_LOGW(TAG, "Bad payload size: %zu", z_slice_len(z_loan(payload)));
    }

    z_drop(z_move(payload));
}

void app_main(void)
{
    esp_err_t ret = nvs_flash_init();
    if (ret == ESP_ERR_NVS_NO_FREE_PAGES || ret == ESP_ERR_NVS_NEW_VERSION_FOUND) {
        ESP_ERROR_CHECK(nvs_flash_erase());
        ret = nvs_flash_init();
    }
    ESP_ERROR_CHECK(ret);

    motor_init();
    wifi_init_sta();

    ESP_LOGI(TAG, "Starting Zenoh (multicast scouting)...");

    z_owned_config_t config;
    z_config_default(&config);
    zp_config_insert(z_loan_mut(config), Z_CONFIG_MODE_KEY, "client");

    z_owned_session_t session;
    while (1) {
        if (z_open(&session, z_move(config), NULL) == Z_OK) {
            ESP_LOGI(TAG, "SUCCESS: Zenoh session opened via scouting!");
            break;
        }
        ESP_LOGE(TAG, "Scouting failed, retrying in 3s...");
        vTaskDelay(3000 / portTICK_PERIOD_MS);
        z_config_default(&config);
        zp_config_insert(z_loan_mut(config), Z_CONFIG_MODE_KEY, "client");
    }

    zp_start_read_task(z_loan_mut(session), NULL);
    zp_start_lease_task(z_loan_mut(session), NULL);

    z_owned_keyexpr_t ke;
    z_keyexpr_from_str(&ke, "robot/drive");

    z_owned_closure_sample_t callback;
    z_closure_sample(&callback, data_handler, NULL, NULL);

    z_owned_subscriber_t sub;
    z_result_t sub_res = z_declare_subscriber(z_loan(session), &sub, z_loan(ke),
                                                z_move(callback), NULL);
    if (sub_res == Z_OK) {
        ESP_LOGI(TAG, "Subscribed to 'robot/drive'");
    } else {
        ESP_LOGE(TAG, "Subscribe failed: %d", sub_res);
    }
    z_drop(z_move(ke));

    while (1) {
        vTaskDelay(1000 / portTICK_PERIOD_MS);
    }
}
