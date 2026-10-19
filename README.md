# EyeCar-Image

Образ Raspberry Pi и контейнер ROS 2 для учебного беспилотного автомобиля АЙКАР (EyeCar).


## Установка одной командой

На чистый Raspberry Pi OS (64 bit) или Debian/Ubuntu:

```bash
curl -fsSL https://raw.githubusercontent.com/Siberias-Last-Hope/EyeCar-Image/main/install.sh | sudo bash
```

Скрипт ставит Docker, udev-правило для Arduino (`/dev/eyecar_arduino`), скачивает
`ghcr.io/siberias-last-hope/eyecar-ros` и запускает его при каждой загрузке (`eyecar.service`).
Другая версия образа: `... | sudo EYECAR_TAG=1.2.3 bash`.

Образ и репозиторий должны быть публичными (GitHub → Packages → eyecar-ros → Package settings → Change visibility → Public).
