# EyeCar-Image

Образ Raspberry Pi и контейнер ROS 2 для учебного беспилотного автомобиля АЙКАР (EyeCar).

> **Статус:** образ ещё не проверен на железе. Контейнер собирается, `colcon build` пакетов проходит,
> но сборка SD-образа и запуск на Raspberry Pi не выполнялись.

## Что внутри

- **SD-образ** (`eyecar-pi-<версия>.img.xz`) для Raspberry Pi 4 и 5, один на обе платы:
  Ubuntu Server 24.04.5 arm64, Docker CE с compose, avahi, ssh, NetworkManager.
  ROS на хост не ставится.
- **Docker-образ `eyecar-ros`** (`linux/arm64` и `linux/amd64`, GHCR): ROS 2 Jazzy, пакеты `eyecar_*`,
  `v4l2_camera`, `teleop_twist_keyboard`, `foxglove_bridge`, `cv_bridge`, OpenCV, pyserial, v4l-utils.
  Вшит в SD-образ и загружается при первой загрузке, интернет на месте не нужен.
- **Пакеты ROS**: `eyecar_base` (связь с Arduino), `eyecar_camera`, `eyecar_teleop`, `eyecar_bringup`
  (`eyecar.launch.py`: камера `/dev/video0` и Foxglove bridge).

Железо: Arduino Mega 2560 по USB (`/dev/eyecar_arduino`, CH340 `1a86:7523`, `2341:0042`, `2341:0010`),
USB-камера `/dev/video0`.

## Структура репозитория

| Папка | Назначение |
|---|---|
| `eyecar_*` | пакеты ROS 2 |
| `docker/` | `ros/Dockerfile` и `compose.yaml` (профили `car` и `pc`) |
| `builder/` | сборщик SD-образа (`build-image.sh` запускается только в CI) |
| `firmware/` | прошивка Arduino |
| `.github/workflows/` | `docker.yml` (контейнер в GHCR), `pi-image.yml` (SD-образ в релиз); оба только на публикацию релиза |

`builder/`, `docker/` и `firmware/` содержат `COLCON_IGNORE`.

## Как собрать

Контейнер (на ПК или на Pi):

```bash
docker compose -f docker/compose.yaml --profile car up --build   # машина: устройства /dev, privileged
docker compose -f docker/compose.yaml --profile pc up --build    # ноутбук: без устройств, без камеры
```

SD-образ собирает GitHub Actions на `ubuntu-24.04-arm`: публикация релиза (тег `v*`) запускает `docker.yml` и `pi-image.yml`; оба workflow срабатывают только на релиз. `pi-image.yml` ждёт контейнер,
подтягивает его, собирает `eyecar-pi-<версия>.img.xz` и прикладывает его к релизу (файлы больше 2 ГБ режутся на части,
см. `JOIN.txt`). Локально `builder/build-image.sh` не запускайте:
он монтирует loop-устройства и делает chroot.

## Первый запуск

1. Запишите `.img.xz` через Raspberry Pi Imager («Use custom») на SD-карту и включите Pi.
2. При первой загрузке (несколько минут) загружается контейнер и задаётся имя `eyecar-XXXX`,
   где `XXXX` — последние 4 символа серийного номера Pi.
3. Логин `pi`, пароль `raspberry`; пароль нужно сменить при первом входе.
4. Wi-Fi точка доступа: SSID `eyecar-XXXX`, пароль `eyecarwifi`, адрес машины 192.168.11.1.
   Ethernet работает по DHCP.
5. Доступ по ssh: `ssh pi@192.168.11.1` или `ssh pi@eyecar-XXXX.local`.

## Сервис

`eyecar.service` запускает `docker compose --profile car up -d --pull never`. Состояние и логи:

```bash
systemctl status eyecar
docker logs eyecar-car-1
```

## Foxglove

Подключитесь к точке доступа (или к той же сети) и в Foxglove Studio откройте
**Open connection → Foxglove WebSocket**: `ws://192.168.11.1:8765` (или `ws://eyecar-XXXX.local:8765`).
Топики камеры и остальные топики ROS доступны на панелях Image и Raw Messages.

## Лицензия

MIT, см. `LICENSE`.
