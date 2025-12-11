import ssl
import paho.mqtt.client as mqtt

BROKER = "u0d60a60.ala.asia-southeast1.emqxsl.com"
PORT = 8883
USERNAME = "traffic_eye"
PASSWORD = "Traffic_eye123"
TOPIC = "traffic_eye/buzzer"
CA_FILE = "emqx_ca.pem"   # pastikan file ini ada di folder yang sama


def create_client():
    client = mqtt.Client(protocol=mqtt.MQTTv311)
    client.username_pw_set(USERNAME, PASSWORD)

    client.tls_set(
        ca_certs=CA_FILE,
        certfile=None,
        keyfile=None,
        tls_version=ssl.PROTOCOL_TLSv1_2,
    )

    client.connect(BROKER, PORT, keepalive=60)
    client.loop_start()
    return client


client = create_client()


def buzzer_on():
    client.publish(TOPIC, "ON")
    print("[MQTT] BUZZER → ON")


def buzzer_off():
    client.publish(TOPIC, "OFF")
    print("[MQTT] BUZZER → OFF")
