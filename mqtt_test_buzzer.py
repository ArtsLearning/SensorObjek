import ssl
import paho.mqtt.client as mqtt

BROKER = "u0d60a60.ala.asia-southeast1.emqxsl.com"
PORT = 8883
USERNAME = "traffic_eye"
PASSWORD = "Traffic_eye123"
TOPIC = "traffic_eye/buzzer"

CA_FILE = "emqx_ca.pem"   # file sertifikat yang kamu buat

# ------------------------------------
# CALLBACKS
# ------------------------------------
def on_connect(client, userdata, flags, rc):
    print("Connected with result code:", rc)
    if rc == 0:
        print("MQTT connection successful!")
        client.subscribe(TOPIC)
    else:
        print("Failed to connect. Error code:", rc)

def on_message(client, userdata, msg):
    print(f"Message received on {msg.topic}: {msg.payload.decode()}")

# ------------------------------------
# CREATE CLIENT
# ------------------------------------
def create_mqtt_client():
    client = mqtt.Client()
    client.username_pw_set(USERNAME, PASSWORD)

    # TLS CONFIG
    client.tls_set(
        ca_certs=CA_FILE,
        tls_version=ssl.PROTOCOL_TLSv1_2,
    )

    client.on_connect = on_connect
    client.on_message = on_message

    return client

# ------------------------------------
# MAIN
# ------------------------------------
def main():
    client = create_mqtt_client()
    client.connect(BROKER, PORT)
    client.loop_forever()

if __name__ == "__main__":
    main()
