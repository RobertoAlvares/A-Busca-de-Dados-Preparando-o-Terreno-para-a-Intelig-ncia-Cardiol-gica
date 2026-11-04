# Fase 3 · Parte 2 — Transmissão para nuvem e visualização (Fog/Cloud Computing)

**CardioIA — Monitoramento Contínuo: IoT na Saúde**
Roberto Almeida Alvares · RM568265 · Grupo 78 (integrante único) · FIAP 2TIAOR

Entregáveis desta parte:

| Entregável pedido | Onde está |
|---|---|
| Código do ESP32 (Arduino IDE/Wokwi) | [`src/fase3/wokwi/sketch.ino`](../src/fase3/wokwi/sketch.ino) — o mesmo da Parte 1, com o cliente MQTT |
| Export do dashboard no Node-RED | [`src/fase3/node-red/flow_cardioia.json`](../src/fase3/node-red/flow_cardioia.json) |
| Prints evidenciando a aplicação | [`assets/fase3/`](../assets/fase3/) |
| Relatório do fluxo MQTT e da configuração do dashboard | este documento |

## 1. Arquitetura: edge, fog e cloud

```
   EDGE (no paciente)              CLOUD (broker)                 FOG (perto da equipe)
 ┌──────────────────────┐  MQTT  ┌───────────────────────┐ MQTT ┌──────────────────────────┐
 │ ESP32 (Wokwi)         │──────►│ HiveMQ                │─────►│ Node-RED                 │
 │ DHT22 + botão de pulso│ QoS 0 │ broker.hivemq.com:1883│ QoS 1│ valida, reconcilia alerta│
 │ alerta local (LED)    │       │ tópicos cardioia/...  │      │ data a leitura           │
 │ buffer offline 1 440  │       └───────────────────────┘      │ dashboard + notificação  │
 └──────────────────────┘                                        └──────────────────────────┘
```

- **Edge** — o vestível decide o alerta sozinho e guarda os dados quando está
  sem rede (Parte 1).
- **Cloud** — o broker MQTT recebe e distribui as mensagens. Quem publica não
  precisa saber quem vai ler: amanhã o mesmo tópico pode alimentar um banco de
  dados, um prontuário ou outro dashboard sem mudar uma linha do ESP32.
- **Fog** — o Node-RED roda numa máquina local (no hospital, seria um servidor
  da unidade). Ele não confia cegamente no dispositivo: valida, recalcula o
  alerta e reconstrói o horário da coleta antes de mostrar.

## 2. O fluxo de comunicação MQTT

### 2.1 Broker e conexão

| Item | Valor | Observação |
|---|---|---|
| Broker | `broker.hivemq.com`, porta **1883** | broker público da HiveMQ, sem cadastro — adequado para protótipo com dado simulado (ver seção 5) |
| Rede no Wokwi | `Wokwi-GUEST` | rede aberta do simulador, com saída para a internet |
| Biblioteca | `PubSubClient` | cliente MQTT 3.1.1 para Arduino/ESP32 |
| Client ID | `cardioia-rm568265-<MAC>` | único por dispositivo, evita que dois clientes se derrubem |
| Buffer MQTT | 512 bytes | a mensagem tem ~200 bytes; o padrão da biblioteca (256) ficaria no limite |

### 2.2 Tópicos

Hierarquia `cardioia/<identificador do projeto>/<paciente>/<tipo>` — permite
assinar um paciente (`cardioia/rm568265/paciente01/#`) ou todos
(`cardioia/rm568265/+/alerta`) com curingas.

| Tópico | Quem publica | Conteúdo | Retido |
|---|---|---|---|
| `cardioia/rm568265/paciente01/vitais` | ESP32 | toda leitura, em JSON | não |
| `cardioia/rm568265/paciente01/alerta` | ESP32 | só as leituras com alerta (mesmo JSON) | não |
| `cardioia/rm568265/paciente01/status` | ESP32 e o broker | `online` / `offline` | **sim** |

### 2.3 Formato da mensagem

```json
{"seq":42,"t_ms":84012,"atraso_s":0,"temp":38.4,"umid":55.0,"bpm":132,
 "alerta":"febre;taquicardia","origem":"tempo_real","buffer":1,"descartadas":0}
```

| Campo | Significado |
|---|---|
| `seq` | número sequencial da leitura — a nuvem percebe se alguma faltou |
| `t_ms`, `atraso_s` | instante da coleta (relógio interno) e há quantos segundos ela foi feita |
| `temp`, `umid` | DHT22 |
| `bpm` | frequência cardíaca calculada pelos intervalos do botão de pulso |
| `alerta` | decisão do **dispositivo**: `normal` ou motivos separados por `;` |
| `origem` | `tempo_real` ou `buffer` (ficou guardada durante a falta de conexão) |
| `buffer`, `descartadas` | ocupação do buffer no envio e perdas por buffer cheio |

### 2.4 Sequência de uma sessão

1. O ESP32 conecta com **Last Will and Testament (LWT)**: registra no broker a
   mensagem `offline` (retida) no tópico `status`. Logo após conectar, publica
   `online` (retida) no mesmo tópico.
2. Se o vestível **cair sem avisar** (bateria, fora de área), o broker publica
   o `offline` sozinho. O painel fica sabendo que o paciente parou de ser
   monitorado — o silêncio também é informação clínica.
3. Como `status` é **retido**, um dashboard aberto depois recebe o último
   estado na hora, sem esperar a próxima mensagem.
4. Cada leitura sai em `vitais`; se houver alerta, sai também em `alerta`.
5. Ao voltar de um período offline, o ESP32 descarrega o buffer em ordem; cada
   mensagem chega com `origem: "buffer"` e o `atraso_s` correspondente.

### 2.5 QoS

O ESP32 publica com **QoS 0** (o `PubSubClient` só publica em QoS 0). A perda
na rede é compensada por duas coisas da Parte 1: o registro **só é apagado do
buffer depois que a publicação retorna sucesso**, e o campo `seq` deixa
qualquer lacuna visível do lado da nuvem. O Node-RED assina com **QoS 1**.

## 3. Configuração do dashboard (Node-RED)

Pacotes: `node-red` 4 e `node-red-dashboard`. O fluxo inteiro está em
[`flow_cardioia.json`](../src/fase3/node-red/flow_cardioia.json); para
reproduzir: *Menu → Import*, colar o arquivo, *Deploy*, abrir
`http://127.0.0.1:1880/ui`.

### 3.1 Nós do fluxo

| Nó | Tipo | Função |
|---|---|---|
| `vitais` | mqtt in (JSON, QoS 1) | assina o tópico de leituras |
| `Regras de fog` | function, 6 saídas | valida faixa física, recalcula o alerta, reconstrói o horário, separa os valores para cada widget |
| `Grafico BPM` | ui_chart (linha) | **gráfico do sinal vital** — frequência cardíaca nos últimos 10 min |
| `Grafico temperatura` | ui_chart (linha) | temperatura nos últimos 10 min |
| `Gauge temperatura` | ui_gauge | **medidor** de temperatura, faixas azul (< 35), verde, vermelho (> 38) |
| `Gauge BPM` | ui_gauge | medidor de BPM, faixas azul (< 50), verde, vermelho (> 120) |
| `Indicador de alerta` | ui_template | **LED virtual + texto**: verde "NORMAL" ou vermelho "ALERTA" com o motivo |
| `so alertas novos` → `rbe` → `Notificacao automatica` | switch, filter, ui_toast | **alerta automático**: notificação na tela quando surge um alerta ou o motivo muda |
| `log de alertas` | debug | registra cada alerta no console do Node-RED |
| `status (LWT)` → `Status do vestivel` | mqtt in, ui_text | mostra `online`/`offline` vindo do Last Will |
| `Ultima leitura` | ui_text | `seq`, origem, atraso e contadores (recebidas, vindas do buffer, descartadas) |

### 3.2 Limites de alerta (definidos pelo grupo)

| Parâmetro | Alerta se | Motivo exibido |
|---|---|---|
| Frequência cardíaca | **> 120 bpm** | taquicardia |
| Frequência cardíaca | < 50 bpm (e > 0) | bradicardia |
| Frequência cardíaca | 0 (sem batida há 6 s) | sem_pulso |
| Temperatura | **> 38 °C** | febre |
| Temperatura | < 35 °C | hipotermia |

Os mesmos limiares existem no ESP32 e no Node-RED (ver 3.3).

### 3.3 O que a camada de fog faz além de exibir

1. **Valida faixa física.** Temperatura fora de 25–45 °C ou BPM fora de 0–250
   é descartado com aviso — é defeito de sensor, não paciente.
2. **Reconcilia o alerta.** Recalcula o alerta com os mesmos limiares e avisa
   no log se o resultado divergir do que o dispositivo mandou (firmware
   desatualizado, por exemplo). É defesa em profundidade: o alarme não depende
   de um único ponto.
3. **Reconstrói o horário.** O ESP32 do simulador não tem relógio real. O fog
   calcula `horário da coleta = agora − atraso_s` e passa isso como
   `msg.timestamp` ao gráfico. Resultado: leituras que chegam atrasadas, vindas
   do buffer, aparecem **no ponto do tempo em que foram medidas**, preenchendo
   a lacuna do período offline em vez de se amontoarem no instante da
   reconexão.
4. **Notifica sem inundar.** O filtro `rbe` só deixa passar a notificação
   quando o motivo do alerta muda — a equipe não recebe 30 avisos iguais por
   minuto (fadiga de alarme é um risco conhecido em UTI).

## 4. Evidências (sessão de teste de 04/11/2026)

| Momento | O que o dashboard mostrou | Print |
|---|---|---|
| Leituras 1–4, 36,6 °C, ~78 bpm | LED virtual verde **NORMAL**, gauges na faixa verde, status `online` | [`dashboard_normal.png`](../assets/fase3/dashboard_normal.png) |
| Leituras 5–6, DHT22 ajustado para 38,6 °C e pulso acelerado (136–139 bpm) | LED virtual vermelho **ALERTA — febre + taquicardia**, gauges no vermelho | [`dashboard_alerta.png`](../assets/fase3/dashboard_alerta.png) |
| Chave em offline | status **`offline`** publicado no tópico `status` | [`dashboard_offline.png`](../assets/fase3/dashboard_offline.png) |
| Chave de volta em online | leituras 7–9 chegam do buffer (`do buffer: 3`), notificação automática **"taquicardia (36,9 °C, 139 bpm)"** — o motivo mudou de "febre + taquicardia" para "taquicardia" | [`dashboard_sync_notificacao.png`](../assets/fase3/dashboard_sync_notificacao.png) |

O log integral do Monitor Serial está em
[`serial_wokwi_04-11-2026.log`](../assets/fase3/serial_wokwi_04-11-2026.log), e o
log do Node-RED registrou os três alertas no mesmo horário dos prints
(`sem_pulso` na 1ª leitura, antes do primeiro batimento; `febre + taquicardia`;
`taquicardia`).

**Uma observação honesta sobre o horário reconstruído.** No navegador usado no
teste, o Wokwi rodou a cerca de 3% do tempo real: 2 s simulados levavam cerca
de 1 minuto de relógio. O `atraso_s` é medido no tempo **simulado** (6, 4 e 2
segundos), enquanto o período offline durou uns 3 minutos de relógio. Por isso,
no gráfico, as leituras do buffer aparecem logo antes da reconexão e não
espalhadas pela lacuna. Num ESP32 real, os dois relógios coincidem e a
reconstrução preenche a lacuna no ponto certo.

## 5. Eficiência, segurança e boas práticas em IoT médico

**Eficiência.** MQTT tem cabeçalho de 2 bytes e conexão persistente: muito mais
leve que abrir uma requisição HTTP por leitura, o que importa num vestível a
bateria. O `delay(10)` no laço e a amostragem de 1/minuto no produto reduzem
consumo. O alerta é decidido no próprio dispositivo, sem ida e volta à nuvem.

**Segurança — o que este protótipo NÃO tem e um produto teria que ter:**

| Risco no protótipo | Por que é aceitável aqui | Controle em produção |
|---|---|---|
| Broker público, porta 1883 **sem TLS** | só trafega **dado simulado**, sem identificação de pessoa | broker privado (ex.: HiveMQ Cloud) em **8883 com TLS** |
| Sem autenticação; qualquer um pode assinar ou publicar no tópico | idem | usuário/senha ou certificado por dispositivo e **ACL por tópico** (cada vestível só publica no próprio tópico) |
| Tópico com "paciente01" | não é identificador real | usar pseudônimo; a ligação pseudônimo ↔ paciente fica no prontuário, nunca no dispositivo nem no broker |
| SSID/senha no código | a rede do Wokwi é aberta | provisionamento seguro (ex.: Wi-Fi provisioning por BLE) e segredos fora do firmware |
| Buffer em RAM sem cifra | dado simulado | cifrar o que for persistido em flash/microSD |

**Dado de saúde é dado pessoal sensível** (LGPD, art. 5º, II). Se este fluxo
recebesse dado de paciente real, cada linha da coluna "controle em produção"
deixaria de ser boa prática e passaria a ser requisito, junto com
**minimização** (o vestível só envia o necessário para o alerta), registro de
acesso e definição de quem responde pelo tratamento.

**Limites declarados.** Sinais simulados; limiares definidos pelo autor **sem
validação clínica**; o protótipo apoia a decisão da equipe de saúde e não
substitui avaliação médica.
