# Fase 3 · Parte 1 — Armazenamento e processamento local (Edge Computing)

**CardioIA — Monitoramento Contínuo: IoT na Saúde**
Roberto Almeida Alvares · RM568265 · Grupo 78 (integrante único) · FIAP 2TIAOR

Entregáveis desta parte:

| Entregável pedido | Onde está |
|---|---|
| Link do projeto no Wokwi | README, seção "Fase 3" (e no topo deste repositório) |
| Código em C++ comentado | [`src/fase3/wokwi/sketch.ino`](../src/fase3/wokwi/sketch.ino) (circuito em [`diagram.json`](../src/fase3/wokwi/diagram.json)) |
| Relatório do fluxo de funcionamento e da lógica de resiliência | este documento |

## 1. O que o protótipo simula

Um **vestível de monitoramento cardíaco** para o paciente que recebeu alta e vai
para casa. O ESP32 lê os sinais vitais, decide sozinho se há alerta, guarda as
leituras enquanto está sem conexão e as envia para a nuvem quando a conexão volta.

## 2. Sensores (mínimo de 2 distintos)

| # | Sensor | Pino | O que mede no CardioIA |
|---|---|---|---|
| 1 | **DHT22** (obrigatório) | GPIO 15 | **temperatura** corporal simulada e **umidade** — o DHT22 conta como 1 sensor, como diz o enunciado |
| 2 | **Botão de pulso** (livre escolha) | GPIO 4 | cada aperto é **um batimento**; o ESP32 calcula a **frequência cardíaca (BPM)** |

Componentes de apoio: **chave deslizante** (GPIO 5) que simula a conectividade,
**LED vermelho** (GPIO 2) de alerta local e **LED verde** (GPIO 18) de "online e
sincronizado".

**Como o BPM é calculado.** O botão é lido sem bloquear o programa, com debounce
de 30 ms, e o instante de cada aperto vai para uma fila das últimas 5 batidas.
BPM = 60 000 ÷ média dos intervalos entre essas batidas. Se não houver batida há
mais de 6 s, o BPM vale 0 e o sistema sinaliza `sem_pulso`. Apertar o botão
uma vez por segundo dá 60 bpm; duas vezes por segundo, 120 bpm.

## 3. Fluxo de funcionamento

```
 a cada 2 s (no produto: 1 por minuto)
 ┌───────────┐   ┌────────────────────┐   ┌─────────────────┐   ┌──────────────────────┐
 │ CAPTURA   │──►│ PROCESSAMENTO LOCAL │──►│ BUFFER OFFLINE  │──►│ TRANSMISSÃO           │
 │ DHT22     │   │ valida leitura      │   │ toda leitura    │   │ online? descarrega o  │
 │ botão→BPM │   │ calcula alertas     │   │ entra aqui      │   │ buffer: Serial.println│
 └───────────┘   │ acende LED alerta   │   │ (fila circular) │   │ + MQTT, depois apaga  │
                 └────────────────────┘   └─────────────────┘   │ offline? só guarda    │
                                                                 └──────────────────────┘
```

1. **Captura.** A cada `INTERVALO_LEITURA_MS` o ESP32 lê temperatura e umidade
   do DHT22. Leitura inválida (NaN) é descartada e registrada no Serial — nunca
   vira dado falso.
2. **Processamento local (edge).** O próprio ESP32 compara os valores com os
   limiares e monta uma máscara de alertas: **febre** (> 38 °C), **hipotermia**
   (< 35 °C), **taquicardia** (> 120 bpm), **bradicardia** (< 50 bpm) e
   **sem pulso** (0 bpm). O LED vermelho acende **na hora, com ou sem internet**.
   Esse é o ponto central do edge computing em saúde: o alarme não pode esperar a
   nuvem responder.
3. **Armazenamento local.** Toda leitura entra primeiro no buffer, inclusive
   quando há conexão. Assim existe um único caminho de envio, e o caso "online"
   é só o caso particular de um buffer com 1 registro.
4. **Transmissão.** Com a conectividade simulada ligada e o MQTT conectado, o
   buffer é descarregado da leitura **mais antiga para a mais nova**. Cada
   registro é impresso com `Serial.println` (o "envio para a nuvem" pedido na
   Parte 1) e publicado no broker MQTT (Parte 2). **Só depois** de publicado ele
   é apagado do buffer.

## 4. Simulação da conectividade (a variável booleana)

A variável `wifiSimulado` é o estado de conexão pedido no enunciado. Ela é
controlada pela **chave deslizante** do circuito, para que se possa ligar e
desligar a conexão com um clique durante a simulação:

- chave à direita → `wifiSimulado = true` → conecta Wi-Fi e MQTT e sincroniza;
- chave à esquerda → `wifiSimulado = false` → publica `offline` no tópico de
  status, desconecta e passa a **só guardar** (`[OFFLINE] guardada seq=...` no
  Monitor Serial).

## 5. Lógica de resiliência offline

**Por que buffer em RAM e não SPIFFS.** O enunciado deixa o SPIFFS opcional
porque ele é volátil no Wokwi: o arquivo some quando a simulação termina. Por
isso o armazenamento local é um **buffer circular em RAM**, e o **Monitor Serial
funciona como registro de resiliência** (alternativa que o próprio enunciado
aceita). Em um ESP32 físico, o mesmo buffer seria gravado em SPIFFS ou cartão
microSD sem mudar a lógica.

**Estratégia de armazenamento limitado (alinhada ao modelo de negócio).**

| Decisão | Valor | Justificativa |
|---|---|---|
| Frequência de amostragem no produto | 1 leitura por minuto | suficiente para tendência de temperatura e de frequência cardíaca em repouso; o simulador usa 2 s só para a demonstração andar |
| Autonomia offline | **24 horas** | cobre o trajeto de volta para casa após a alta, uma noite sem Wi-Fi ou uma queda de internet de um dia |
| Capacidade do buffer | **1 440 leituras** (`CAPACIDADE_BUFFER`) | 24 h × 60 leituras/h |
| Memória ocupada | ~28 KB (1 440 × 20 bytes por registro) | cabe com folga nos 320 KB de RAM do ESP32 |
| Buffer cheio | descarta a **mais antiga** e soma em `descartadas` | para decisão clínica o dado recente vale mais; o contador torna a perda **visível** em vez de silenciosa |

**Garantias da sincronização.**

- **Ordem preservada:** envia do mais antigo para o mais novo, então o histórico
  chega na sequência certa.
- **Nada se apaga antes de ser enviado:** se a publicação falhar no meio da
  descarga, o laço para e o restante continua no buffer para o próximo ciclo.
- **Rastreabilidade:** cada registro leva `seq` (número sequencial — a nuvem
  percebe se algum faltou), `origem` (`buffer` ou `tempo_real`), `atraso_s`
  (quanto tempo ficou guardado) e `descartadas`.
- **Coleta não para:** offline, o laço continua lendo sensores, calculando BPM e
  acendendo o LED de alerta; só a transmissão fica suspensa.

## 6. Teste realizado no Wokwi (04/11/2026)

Trecho real do Monitor Serial (log integral em
[`assets/fase3/serial_wokwi_04-11-2026.log`](../assets/fase3/serial_wokwi_04-11-2026.log)):

```
[REDE] modo OFFLINE - gravando so no buffer
[OFFLINE] guardada seq=7 temp=38.6 bpm=140 alerta=febre;taquicardia | buffer=1/1440
[OFFLINE] guardada seq=8 temp=38.6 bpm=136 alerta=febre;taquicardia | buffer=2/1440
[OFFLINE] guardada seq=9 temp=36.9 bpm=139 alerta=taquicardia | buffer=3/1440
[REDE] modo ONLINE
[MQTT] conectado ao broker
[SYNC] conexao de volta: enviando 3 leitura(s) guardada(s) offline + a atual
{"seq":7,"t_ms":15093,"atraso_s":6,"temp":38.6,...,"alerta":"febre;taquicardia","origem":"buffer","buffer":4,...}
{"seq":8,"t_ms":17100,"atraso_s":4,"temp":38.6,...,"alerta":"febre;taquicardia","origem":"buffer","buffer":3,...}
{"seq":9,"t_ms":19107,"atraso_s":2,"temp":36.9,...,"alerta":"taquicardia","origem":"buffer","buffer":2,...}
{"seq":10,"t_ms":21107,"atraso_s":0,"temp":36.9,...,"alerta":"normal","origem":"tempo_real","buffer":1,...}
```

O que o trecho comprova:

1. **Coleta contínua offline:** as leituras 7, 8 e 9 foram feitas e guardadas
   sem conexão; o buffer subiu de 1 para 3.
2. **Alerta local sem internet:** com 38,6 °C e 140 bpm o alerta foi decidido
   no dispositivo e o LED vermelho ficou aceso durante o período offline.
3. **Sincronização em ordem e sem perda:** na volta, as 3 guardadas saem da
   mais antiga para a mais nova (`seq` 7, 8, 9), marcadas `origem: buffer`, com
   o atraso de cada uma (6, 4, 2 s), seguidas da leitura atual. O campo
   `buffer` desce a cada envio até 1 (a atual) e nada foi descartado.
4. **Nenhuma lacuna na nuvem:** o Node-RED contou 10 leituras recebidas, 3 delas
   vindas do buffer — `seq` de 1 a 10 sem buraco (print
   [`dashboard_sync_notificacao.png`](../assets/fase3/dashboard_sync_notificacao.png)).

O pulso foi gerado acionando o botão do simulador por script, em ritmo controlado (≈ 78 e ≈ 140 bpm), e a temperatura,
ajustando o DHT22 no próprio simulador.

## 7. Limitações declaradas

- Os sinais são **simulados** (botão no lugar de sensor óptico de pulso,
  temperatura ajustada à mão). Os limiares foram definidos pelo autor a partir
  de referências gerais, **sem validação clínica**.
- O buffer em RAM se perde se o dispositivo desligar. Em hardware real a
  persistência iria para SPIFFS/microSD — o ponto que o enunciado reconhece como
  "ir além".
- O ESP32 não tem relógio de tempo real no simulador; o horário da coleta é
  reconstruído na nuvem a partir de `atraso_s` (ver relatório da Parte 2).
