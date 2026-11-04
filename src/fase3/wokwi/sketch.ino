/*
 * CardioIA — Fase 3 · Monitoramento Contínuo (IoT na Saúde)
 * Vestível cardíaco simulado em ESP32 (Wokwi).
 *
 * Autor: Roberto Almeida Alvares — RM568265 — FIAP 2TIAOR
 *
 * FLUXO: captura -> processamento local (edge) -> buffer offline
 *        -> transmissão MQTT (nuvem) -> dashboard Node-RED -> alerta
 *
 * SENSORES (2 distintos, como pede o enunciado):
 *   1. DHT22 (GPIO 15) ........ temperatura corporal simulada + umidade
 *   2. Botão de pulso (GPIO 4)  cada aperto = 1 batimento; o ESP32 calcula
 *                               a frequência cardíaca (BPM) pelos intervalos.
 *
 * ATUADORES / CONTROLES:
 *   - Chave deslizante (GPIO 5): simula a conectividade. É a "variável
 *     booleana" de Wi-Fi do enunciado (wifiSimulado). Chave para a direita =
 *     online; para a esquerda = offline (paciente fora de área).
 *   - LED vermelho (GPIO 2): alerta LOCAL. Acende mesmo sem internet — o
 *     alarme não pode depender da nuvem (é o papel do edge computing).
 *   - LED verde (GPIO 18): online e sincronizado com o broker.
 *
 * RESILIÊNCIA OFFLINE:
 *   SPIFFS é volátil no simulador (o próprio enunciado avisa), então o
 *   armazenamento local é um BUFFER CIRCULAR em RAM com capacidade fixa
 *   (CAPACIDADE_BUFFER). Toda leitura entra no buffer primeiro. Quando a
 *   conexão volta, o buffer é descarregado em ordem (mais antiga primeiro):
 *   cada registro vai pelo Serial.println E pelo MQTT, e só então é apagado.
 *   Se o buffer enche, a leitura mais antiga é descartada e contada em
 *   "descartadas" — o dado recente vale mais para decisão clínica.
 */

#include <WiFi.h>
#include <PubSubClient.h>
#include "DHTesp.h"

// ---------------------------------------------------------------- pinos
const int PINO_DHT       = 15;
const int PINO_PULSO     = 4;
const int PINO_CHAVE_NET = 5;
const int PINO_LED_ALERTA = 2;
const int PINO_LED_ONLINE = 18;

// ---------------------------------------------------------------- rede
// "Wokwi-GUEST" é a rede aberta do simulador. Num dispositivo real, SSID e
// senha viriam de provisionamento seguro, nunca fixos no código.
const char* WIFI_SSID  = "Wokwi-GUEST";
const char* WIFI_SENHA = "";

// Broker público da HiveMQ (porta 1883, sem TLS). Adequado SÓ para protótipo
// com dado simulado — ver relatório, seção de segurança.
const char* MQTT_BROKER = "broker.hivemq.com";
const int   MQTT_PORTA  = 1883;
const char* TOPICO_VITAIS = "cardioia/rm568265/paciente01/vitais";
const char* TOPICO_ALERTA = "cardioia/rm568265/paciente01/alerta";
const char* TOPICO_STATUS = "cardioia/rm568265/paciente01/status";

// ---------------------------------------------------------------- regras
// Intervalo de amostragem. No simulador: 2 s, para a demonstração andar.
// No produto (ver relatório): 1 leitura por minuto.
const unsigned long INTERVALO_LEITURA_MS = 2000;

// Capacidade do buffer offline. Modelo de negócio: 1 leitura/min durante
// 24 h sem conexão = 1440 registros (~28 KB de RAM: 20 bytes cada, folgado nos 320 KB do
// ESP32). Um dia inteiro fora de área cobre a ida do paciente para casa
// depois da alta e uma noite sem Wi-Fi.
const int CAPACIDADE_BUFFER = 1440;

// Limiares clínicos de alerta (definidos pelo grupo; sem validação médica).
const float LIMITE_TEMP_FEBRE   = 38.0;  // °C
const float LIMITE_TEMP_HIPO    = 35.0;  // °C
const int   LIMITE_BPM_TAQUI    = 120;   // bpm
const int   LIMITE_BPM_BRADI    = 50;    // bpm
const unsigned long SEM_PULSO_MS = 6000; // sem batimento há 6 s -> BPM = 0

// ---------------------------------------------------------------- tipos
struct Leitura {
  uint32_t seq;        // número sequencial (detecta perda na nuvem)
  uint32_t t_ms;       // millis() da coleta (sem RTC no simulador)
  float    temp;       // °C
  float    umid;       // %
  uint16_t bpm;        // batimentos por minuto
  uint8_t  alerta;     // máscara de bits, ver ALERTA_*
};

const uint8_t ALERTA_FEBRE  = 1 << 0;
const uint8_t ALERTA_HIPO   = 1 << 1;
const uint8_t ALERTA_TAQUI  = 1 << 2;
const uint8_t ALERTA_BRADI  = 1 << 3;
const uint8_t ALERTA_SEM_PULSO = 1 << 4;

// ---------------------------------------------------------------- estado
DHTesp dht;
WiFiClient redeCliente;
PubSubClient mqtt(redeCliente);

Leitura buffer[CAPACIDADE_BUFFER];
int inicioBuf = 0;          // índice da leitura mais antiga
int totalBuf  = 0;          // quantas leituras estão guardadas
uint32_t descartadas = 0;   // leituras perdidas por buffer cheio
uint32_t proximoSeq  = 1;

bool wifiSimulado = false;  // a "variável booleana" de conectividade
unsigned long ultimaLeitura = 0;

// Detecção de batimentos pelo botão (com debounce)
const int JANELA_BATIDAS = 5;          // média dos últimos 4 intervalos
unsigned long batidas[JANELA_BATIDAS];
int nBatidas = 0;
bool botaoAnterior = HIGH;
unsigned long ultimaMudancaBotao = 0;

// ================================================================ buffer
// Guarda a leitura no fim da fila. Cheio? Descarta a mais antiga.
void bufferGuardar(const Leitura& l) {
  if (totalBuf == CAPACIDADE_BUFFER) {
    inicioBuf = (inicioBuf + 1) % CAPACIDADE_BUFFER;
    totalBuf--;
    descartadas++;
  }
  int fim = (inicioBuf + totalBuf) % CAPACIDADE_BUFFER;
  buffer[fim] = l;
  totalBuf++;
}

// ================================================================ sensores
// Registra uma batida no histórico (fila deslizante de instantes).
void registrarBatida(unsigned long agora) {
  if (nBatidas < JANELA_BATIDAS) {
    batidas[nBatidas++] = agora;
  } else {
    for (int i = 1; i < JANELA_BATIDAS; i++) batidas[i - 1] = batidas[i];
    batidas[JANELA_BATIDAS - 1] = agora;
  }
}

// Lê o botão sem bloquear. Conta a batida na borda de descida (apertou).
void lerBotaoPulso() {
  bool estado = digitalRead(PINO_PULSO);
  unsigned long agora = millis();
  if (estado != botaoAnterior && agora - ultimaMudancaBotao > 30) {
    ultimaMudancaBotao = agora;
    if (estado == LOW) registrarBatida(agora);
    botaoAnterior = estado;
  }
}

// BPM = 60000 / média dos intervalos entre batidas recentes.
// Sem batida há SEM_PULSO_MS, ou menos de 2 batidas: 0.
uint16_t calcularBpm() {
  if (nBatidas < 2) return 0;
  if (millis() - batidas[nBatidas - 1] > SEM_PULSO_MS) return 0;
  unsigned long soma = batidas[nBatidas - 1] - batidas[0];
  float media = (float)soma / (nBatidas - 1);
  if (media <= 0) return 0;
  return (uint16_t)(60000.0 / media + 0.5);
}

uint8_t avaliarAlertas(float temp, uint16_t bpm) {
  uint8_t a = 0;
  if (temp > LIMITE_TEMP_FEBRE) a |= ALERTA_FEBRE;
  if (temp < LIMITE_TEMP_HIPO)  a |= ALERTA_HIPO;
  if (bpm == 0)                 a |= ALERTA_SEM_PULSO;
  else if (bpm > LIMITE_BPM_TAQUI) a |= ALERTA_TAQUI;
  else if (bpm < LIMITE_BPM_BRADI) a |= ALERTA_BRADI;
  return a;
}

// Texto legível da máscara de alertas, para o dashboard.
String textoAlerta(uint8_t a) {
  if (a == 0) return "normal";
  String s = "";
  if (a & ALERTA_FEBRE)     s += "febre;";
  if (a & ALERTA_HIPO)      s += "hipotermia;";
  if (a & ALERTA_TAQUI)     s += "taquicardia;";
  if (a & ALERTA_BRADI)     s += "bradicardia;";
  if (a & ALERTA_SEM_PULSO) s += "sem_pulso;";
  s.remove(s.length() - 1);
  return s;
}

// ================================================================ rede
void conectarWifi() {
  if (WiFi.status() == WL_CONNECTED) return;
  WiFi.begin(WIFI_SSID, WIFI_SENHA, 6);  // canal 6 acelera no Wokwi
  unsigned long t0 = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - t0 < 10000) {
    lerBotaoPulso();
    delay(50);
  }
  Serial.println(WiFi.status() == WL_CONNECTED
                 ? "[REDE] Wi-Fi conectado"
                 : "[REDE] Wi-Fi indisponivel, sigo offline");
}

bool conectarMqtt() {
  if (mqtt.connected()) return true;
  if (WiFi.status() != WL_CONNECTED) return false;
  String id = "cardioia-rm568265-" + String((uint32_t)ESP.getEfuseMac(), HEX);
  // Last Will: se o vestível cair sem avisar, o broker publica "offline".
  if (mqtt.connect(id.c_str(), TOPICO_STATUS, 1, true, "offline")) {
    mqtt.publish(TOPICO_STATUS, "online", true);
    Serial.println("[MQTT] conectado ao broker");
    return true;
  }
  Serial.print("[MQTT] falha, rc=");
  Serial.println(mqtt.state());
  return false;
}

// Monta o JSON de uma leitura. "origem" diz se veio do buffer (atrasada)
// ou em tempo real; "atraso_s" mostra quanto tempo ficou guardada.
String paraJson(const Leitura& l, const char* origem) {
  char json[256];
  snprintf(json, sizeof(json),
    "{\"seq\":%lu,\"t_ms\":%lu,\"atraso_s\":%lu,\"temp\":%.1f,\"umid\":%.1f,"
    "\"bpm\":%u,\"alerta\":\"%s\",\"origem\":\"%s\",\"buffer\":%d,\"descartadas\":%lu}",
    (unsigned long)l.seq, (unsigned long)l.t_ms,
    (unsigned long)((millis() - l.t_ms) / 1000),
    l.temp, l.umid, l.bpm, textoAlerta(l.alerta).c_str(), origem,
    totalBuf, (unsigned long)descartadas);
  return String(json);
}

// Descarrega o buffer: mais antiga primeiro. Só apaga depois de enviar.
// Se a publicação falhar no meio, para e tenta de novo no próximo ciclo,
// sem perder nada.
void sincronizarBuffer() {
  if (totalBuf == 0) return;
  int pendentes = totalBuf;
  if (pendentes > 1) {  // 1 só = a leitura que acabou de ser feita
    Serial.print("[SYNC] conexao de volta: enviando ");
    Serial.print(pendentes - 1);
    Serial.println(" leitura(s) guardada(s) offline + a atual");
  }
  while (totalBuf > 0) {
    const Leitura& l = buffer[inicioBuf];
    // A leitura mais recente é "tempo_real"; as anteriores esperaram offline.
    const char* origem = (l.seq == proximoSeq - 1) ? "tempo_real" : "buffer";
    String json = paraJson(l, origem);
    if (!mqtt.publish(TOPICO_VITAIS, json.c_str())) {
      Serial.println("[SYNC] publicacao falhou; mantenho no buffer");
      return;
    }
    if (l.alerta) mqtt.publish(TOPICO_ALERTA, json.c_str());
    Serial.println(json);  // "envio para a nuvem via Serial.println"
    inicioBuf = (inicioBuf + 1) % CAPACIDADE_BUFFER;  // apaga o registro
    totalBuf--;
    mqtt.loop();
    lerBotaoPulso();
  }
}

// ================================================================ setup / loop
void setup() {
  Serial.begin(115200);
  pinMode(PINO_PULSO, INPUT_PULLUP);
  pinMode(PINO_CHAVE_NET, INPUT_PULLUP);
  pinMode(PINO_LED_ALERTA, OUTPUT);
  pinMode(PINO_LED_ONLINE, OUTPUT);
  dht.setup(PINO_DHT, DHTesp::DHT22);
  mqtt.setServer(MQTT_BROKER, MQTT_PORTA);
  mqtt.setBufferSize(512);
  // Keepalive: intervalo máximo sem tráfego antes de o broker considerar o
  // cliente morto (e disparar o Last Will "offline"). No Wokwi o tempo
  // simulado corre bem mais devagar que o relógio do broker, então o padrão
  // de 15 s derrubava a conexão a cada leitura. Num vestível real, 60 s.
  mqtt.setKeepAlive(300);
  Serial.println("CardioIA - vestivel cardiaco (Fase 3) iniciado");
  Serial.print("Buffer offline: ");
  Serial.print(CAPACIDADE_BUFFER);
  Serial.println(" leituras");
}

void loop() {
  // Pausa curta: economiza energia (vestível a bateria) e deixa o simulador
  // rodar em tempo real. 10 ms ainda pega qualquer aperto do botão de pulso.
  delay(10);
  lerBotaoPulso();

  // Chave para a direita (lê HIGH) = conectividade simulada ligada.
  bool chaveOnline = digitalRead(PINO_CHAVE_NET) == HIGH;
  if (chaveOnline != wifiSimulado) {
    wifiSimulado = chaveOnline;
    Serial.println(wifiSimulado ? "[REDE] modo ONLINE" : "[REDE] modo OFFLINE - gravando so no buffer");
    if (!wifiSimulado) {
      if (mqtt.connected()) { mqtt.publish(TOPICO_STATUS, "offline", true); mqtt.disconnect(); }
    }
  }

  if (wifiSimulado) {
    conectarWifi();
    if (conectarMqtt()) mqtt.loop();
  }
  digitalWrite(PINO_LED_ONLINE, wifiSimulado && mqtt.connected());

  if (millis() - ultimaLeitura < INTERVALO_LEITURA_MS) return;
  ultimaLeitura = millis();

  // 1) captura
  TempAndHumidity th = dht.getTempAndHumidity();
  if (isnan(th.temperature) || isnan(th.humidity)) {
    Serial.println("[SENSOR] leitura do DHT22 invalida, descartada");
    return;
  }
  uint16_t bpm = calcularBpm();

  // 2) processamento local: alerta decidido no próprio dispositivo
  Leitura l;
  l.seq = proximoSeq++;
  l.t_ms = millis();
  l.temp = th.temperature;
  l.umid = th.humidity;
  l.bpm = bpm;
  l.alerta = avaliarAlertas(l.temp, l.bpm);
  digitalWrite(PINO_LED_ALERTA, l.alerta ? HIGH : LOW);

  // 3) armazenamento local: TODA leitura passa pelo buffer
  bufferGuardar(l);

  // 4) transmissão: online -> descarrega o buffer; offline -> só registra
  if (wifiSimulado && mqtt.connected()) {
    sincronizarBuffer();
  } else {
    Serial.print("[OFFLINE] guardada seq=");
    Serial.print(l.seq);
    Serial.print(" temp=");
    Serial.print(l.temp, 1);
    Serial.print(" bpm=");
    Serial.print(l.bpm);
    Serial.print(" alerta=");
    Serial.print(textoAlerta(l.alerta));
    Serial.print(" | buffer=");
    Serial.print(totalBuf);
    Serial.print("/");
    Serial.println(CAPACIDADE_BUFFER);
  }
}
