# Портирование Asterisk Plus Enterprise в Asterisk Plus (Community)

> **Статус:** Фаза 1 и Фаза 2 завершены. Мультикомпанийная поддержка исключена из скоупа.

## Обзор

Модуль **Asterisk Plus Enterprise** (`asterisk_plus_enterprise`) расширяет базовый модуль `asterisk_plus`, снимая ограничения readonly с ряда полей и добавляя бизнес-логику. Дополнительно существует модуль **Asterisk Plus Multicompany** (`asterisk_plus_multicompany`), который добавляет мультикомпанийную поддержку.

Цель: перенести ВСЮ функциональность из обоих EE-модулей в базовый `asterisk_plus`, чтобы не требовалось отдельных Enterprise-модулей.

---

## Часть 1: Список фичей Enterprise

### 1.1 Asterisk Plus Enterprise (v1.1.0)

| # | Фича | Файл EE | Модель | Описание |
|---|-------|---------|--------|----------|
| 1 | **Авто-создание контактов** | `models/channel.py` | `asterisk_plus.channel` | При входящем звонке, если контакт не найден и включена настройка `auto_create_partners`, автоматически создается `res.partner` с номером телефона |
| 2 | **Авто-создание PBX-пользователей** | `models/server.py` | `asterisk_plus.server` | Метод `run_auto_create_pbx_users()` — автоматически создает PBX-пользователей для всех Odoo-пользователей с группой asterisk_plus |
| 3 | **Генерация SIP-пиров** | `models/server.py` | `asterisk_plus.server` | Метод `get_sip_peers()` — генерирует SIP-конфигурацию на основе шаблонов с динамическими паролями, расширениями, CallerID |
| 4 | **Применение SIP-конфигурации** | `models/user.py` | `asterisk_plus.user` | Метод `apply_sip_peers()` — отправляет задание агенту на скачивание и применение SIP-конфигурации. Кнопка "Apply SIP Channels" |
| 5 | **FAGI-маршрутизация** | `models/user.py` | `asterisk_plus.user` | Метод `fagi_request()` — AGI-обработчик для маршрутизации вызовов: поиск пользователя по DID/extension, динамический набор каналов с записью |
| 6 | **MP3-кодирование записей** | `models/recording.py` | `asterisk_plus.recording` | В `get_all_recording_data()` — если включен `use_mp3_encoder`, запись конвертируется в MP3 с настраиваемым битрейтом и качеством |
| 7 | **Выборочная транскрипция** | `models/recording.py` | `asterisk_plus.recording` | В `get_transcript()` — проверка правил транскрипции перед обработкой |
| 8 | **Миграция хранилища записей** | `models/settings.py` | `asterisk_plus.settings` | Метод `sync_recording_storage()` — перенос записей между БД и файловым хранилищем с garbage collection |
| 9 | **Расширенные типы хранилища** | `models/settings.py` | `asterisk_plus.settings` | Поле `recordings_access` расширено вариантами: 'remote', 'asterisk_http', 's3' |
| 10 | **Отключение форматирования телефонов** | `models/res_partner.py` | `res.partner` | Если включен `disable_phone_format`, номера не нормализуются — возвращаются как есть |
| 11 | **Динамическая операция поиска** | `models/res_partner.py` | `res.partner` | Метод `search_by_number()` читает настройку `number_search_operation` ('=' или contains) |
| 12 | **Визард отчета по звонкам** | `wizard/call.py` | `asterisk_plus.call_wizard` | Метод `submit()` — расширенная фильтрация по дате, пользователям, партнерам, статусу + генерация отчета |

### 1.2 Разблокировка полей (readonly -> editable)

Enterprise снимает `readonly="1"` со следующих полей через наследование views:

**Settings (`views/settings.xml`):**
- `auto_create_partners` — авто-создание контактов
- `calls_keep_days` — срок хранения звонков
- `number_search_operation` — тип поиска номера
- `disable_phone_format` — отключение форматирования
- `recordings_keep_days` — срок хранения записей
- `use_mp3_encoder` — MP3-кодирование
- `mp3_encoder_bitrate` — битрейт MP3
- `mp3_encoder_quality` — качество MP3
- `recording_storage` — хранилище записей
- `transcription_rules` — правила транскрипции

**Server (`views/server.xml`):**
- `auto_create_pbx_users` — авто-создание PBX-пользователей
- `generate_sip_peers` — генерация SIP-пиров

**User (`views/user.xml`):**
- `sip_password` — SIP-пароль
- `sip_transport` — транспорт SIP
- `did_number` — DID-номер
- `callerid_number` — CallerID
- `record_calls` — запись звонков
- `dial_timeout` — таймаут набора

**Call Wizard (`wizard/call.xml`):**
- Добавлена кнопка "Submit" для выполнения отчета

### 1.3 Asterisk Plus Multicompany (v2.0.1)

| # | Фича | Файл | Модель | Описание |
|---|-------|------|--------|----------|
| 13 | **Компания у PBX-пользователя** | `models/user.py` | `asterisk_plus.user` | Поле `company_id` (related к `user.company_id`, stored) |
| 14 | **Компания у звонка** | `models/call.py` | `asterisk_plus.call` | Вычисляемое поле `company_id` — определяется по calling_user → answered_user → partner → ref |
| 15 | **Компания у записи** | `models/recording.py` | `asterisk_plus.recording` | Вычисляемое поле `company_id` — определяется по call → calling_user → answered_user |
| 16 | **Фильтрация по компании** | `views/*.xml` | call, recording | Группировка и фильтр по компании в search views |
| 17 | **Отображение компании** | `views/*.xml` | user, call, recording | Поле company_id в list/form views |

---

## Часть 2: Дорожная карта портирования

### Фаза 0: Подготовка
- [x] ~~Создать ветку `feature/ee-to-community`~~
- [ ] Написать тесты для существующей функциональности community (baseline)
- [ ] Задокументировать текущие ограничения community модуля

### Фаза 1: Снятие ограничений UI — ЗАВЕРШЕНА
**Цель:** Убрать все `readonly="1"` и `help="Enterprise Feature"` из view-файлов community.

| Задача | Файл community | Что сделать | Статус |
|--------|----------------|-------------|--------|
| 1.1 | `views/settings.xml` | Убрать `readonly="1"` с 10 полей | DONE |
| 1.2 | `views/server.xml` | Убрать `readonly="1"` с 2 полей | DONE |
| 1.3 | `views/user.xml` | Убрать `readonly="1"` с 4 полей + показать sip_password, sip_transport + кнопка Apply SIP | DONE |
| 1.4 | `wizard/call.xml` | Добавить кнопку "Submit", убрать "(Enterprise Feature)" из названия | DONE |

---

### Фаза 2: Портирование бизнес-логики — ЗАВЕРШЕНА

| Задача | Исходник EE | Целевой файл community | Что сделано | Статус |
|--------|-------------|------------------------|-------------|--------|
| 2.1 | `ee/models/channel.py` | `models/channel.py` | Авто-создание партнеров в `update_call_partner()` | DONE |
| 2.2 | `ee/models/server.py` | `models/server.py` | `run_auto_create_pbx_users()` в write() + реальный `get_sip_peers()` | DONE |
| 2.3 | `ee/models/user.py` | `models/user.py` | Реальные `apply_sip_peers()` и `fagi_request()` | DONE |
| 2.4 | `ee/models/recording.py` | `models/recording.py` | MP3-логика в `get_all_recording_data()` + правила транскрипции в `get_transcript()` | DONE |
| 2.5 | `ee/models/settings.py` | `models/settings.py` | `sync_recording_storage()` + расширенный RECORDING_ACCESS_SELECTION | DONE |
| 2.6 | `ee/models/res_partner.py` | `models/res_partner.py` | Условная нормализация/форматирование + динамическая операция поиска | DONE |
| 2.7 | `wizard/call.py` | — | Метод `submit()` уже присутствовал в community (идентичный EE-версии) | SKIP |

---

### ~~Фаза 3: Мультикомпанийная поддержка — ИСКЛЮЧЕНА ИЗ СКОУПА~~

---

### Фаза 4: Тестирование
| Задача | Описание | Статус |
|--------|----------|--------|
| 4.1 | Протестировать авто-создание контактов при входящем звонке | TODO |
| 4.2 | Протестировать SIP-генерацию и применение (`get_sip_peers`, `apply_sip_peers`) | TODO |
| 4.3 | Протестировать FAGI-маршрутизацию (`fagi_request`) | TODO |
| 4.4 | Протестировать MP3-кодирование записей (`get_all_recording_data`) | TODO |
| 4.5 | Протестировать миграцию хранилища записей (`sync_recording_storage`) | TODO |
| 4.6 | Протестировать визард отчета по звонкам (кнопка Submit) | TODO |
| 4.7 | Протестировать отключение форматирования телефонов (`disable_phone_format`) | TODO |
| 4.8 | Протестировать правила транскрипции (`transcription_rules`) | TODO |

---

### Фаза 5: Очистка — ЗАВЕРШЕНА
| Задача | Описание | Статус |
|--------|----------|--------|
| 5.1 | Удалить все упоминания "Enterprise Feature" из views | DONE |
| 5.2 | Заменить заглушки на реальную логику | DONE |
| 5.3 | Убрать "(Enterprise Feature)" из названия wizard action | DONE |

---

### Миграция для пользователей с установленным EE

**Важно:** Если у пользователя установлен `asterisk_plus_enterprise`, его uninstall_hook сбрасывает
настройки в дефолты (auto_create_partners=False, generate_sip_peers=False и т.д.).

**Рекомендация:** Сначала обновить `asterisk_plus` до новой версии, затем удалить `asterisk_plus_enterprise`.
После удаления EE проверить, что настройки не сброшены.

---

## Часть 3: Сводная таблица

| Фаза | Описание | Задач | Статус |
|-------|----------|-------|--------|
| 1 | Снятие ограничений UI | 4 | **DONE** |
| 2 | Портирование бизнес-логики | 7 | **DONE** |
| ~~3~~ | ~~Мультикомпанийная поддержка~~ | — | Исключена |
| 4 | Тестирование | 8 | TODO |
| 5 | Очистка | 3 | **DONE** |

---

## Часть 4: Порядок приоритетов

### Высокий приоритет (делать первым)
1. Снятие readonly ограничений (Фаза 1) — минимальные усилия, максимальный эффект
2. Авто-создание контактов (2.1) — часто запрашиваемая фича
3. Визард отчета по звонкам (2.7) — кнопка Submit уже есть в UI

### Средний приоритет
4. MP3-кодирование (2.4) — улучшает работу с записями
5. Гибкий поиск номеров и форматирование (2.6) — удобство
6. Мультикомпанийная поддержка (Фаза 3) — нужна для multi-tenant

### Низкий приоритет (делать последним)
7. SIP-генерация и применение (2.2, 2.3) — специфичная фича
8. FAGI-маршрутизация (2.3) — требует настройки Asterisk
9. Миграция хранилища (2.5) — редко используется

---

## Часть 5: Риски и зависимости

| Риск | Описание | Митигация |
|------|----------|-----------|
| Обратная совместимость | У пользователей может быть установлен EE-модуль | Написать миграционный скрипт (4.1) |
| Конфликт модулей | После портирования EE-модуль будет конфликтовать | Пометить EE как deprecated, проверить в `__manifest__.py` |
| FAGI-логика | Тесно связана с конфигурацией Asterisk | Тестировать на staging с реальным Asterisk |
| Multicompany | Вычисляемые поля company_id могут замедлить массовые операции | Проверить performance на больших объемах данных |
