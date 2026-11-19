# Figma MCP Server Rules

Код приложения ещё не создан. Правила фиксируют, как переносить макет `etolegko_design` в React + Chakra UI.

Макет: https://www.figma.com/design/FoSx9BewXlyoFjRvIcJ3gJ

## Компоненты

- IMPORTANT: UI только из Chakra UI. Свои стили не писать.
- Тема: `src/theme/index.ts`, токены в `src/theme/foundations/`, переопределения компонентов в `src/theme/components/`.
- Примитивы экрана: `src/components/`. Страницы: `src/pages/`.
- Имена компонентов PascalCase, один компонент — один файл, экспорт `export function`.
- `ChakraProvider` и `ColorModeScript` в корне.
- IMPORTANT: цвета только из семантических токенов Chakra, hex в JSX не писать.
- Палитра, светлая: холст `bg.subtle`, карточки `bg`, текст `gray.fg`, приглушённый `fg.muted`, границы `border.subtle`. Акцент `blue.fg` (логотип, активный пункт, заголовки бренда). Вторичный акцент `cyan.fg`.
- Кнопки: стандартный Chakra `Button` `size="sm"`. Главное действие `variant="solid"` `colorPalette="blue"`. Вторичное `variant="outline"` `colorPalette="cyan"`. Свой padding не задавать.
- Статусы: `Badge`. Поиск и оффер: `Input` или `Combobox`. Таблица: `Table`. Пагинация: `Pagination`. Плашка расхождения: `Alert`.

## Оболочка admin

- `login` без сайдбара. На `lg` две колонки: тёмная панель бренда и форма.
- `companies`, `offers`, `company/{id}`, `streams` внутри `AppShell`. Сайдбар: Companies и Offers. Streams только из карточки компании. Контент на `bg.subtle`.
- Интерфейс на английском. Пагинация: текущая страница `solid` `blue`, остальные `outline` `cyan`, как у кнопок.
- Сайдбар: `base` скрыт (меню в `Drawer`), `md` 200px, `lg` 240px.
- Сетка страницы: `base` одна колонка, `md` и `lg` как в макете (8 и 12 колонок через `SimpleGrid` / `Grid`).
- Активный пункт меню: `bg="gray.100"`, текст `gray.900`.

## Figma MCP

1. `get_design_context` для нужного узла.
2. Если ответ обрезан — `get_metadata`, затем точечный `get_design_context`.
3. `get_screenshot` того же узла.
4. Только после этого переносить в код.
5. Вывод MCP (часто React + Tailwind) — референс вёрстки, не итоговый код. IMPORTANT: Tailwind-классы заменять на пропсы Chakra.
6. Сверить результат со скриншотом.

Узлы колонок после обновления оболочки смотреть по именам `Desktop`, `Tablet`, `Mobile` и экранам `login`, `companies`, `company`, `streams`.

## Ассеты

- IMPORTANT: если MCP отдал localhost-URL картинки или SVG, использовать его как есть.
- Не ставить новые пакеты иконок. Иконки — из Chakra (`react-icons` только если их уже нет в макете) либо SVG из ответа Figma.
- Файлы класть в `public/`.

## Проект

- Фронт не вызывает Keitaro. Данные только с API бэкенда.
- Автотесты никогда не ходят на реальный Keitaro — только моки (`MockKeitaroClient` / `httpx.MockTransport`).
- Экраны: вход, список компаний, карточка компании, редактор потоков.
- Доступность: подпись у каждого поля, `as` для семантики, фокус не убирать.
- Color mode Chakra: светлая тема по умолчанию, тёмная через `useColorMode`.
- Тяжёлые блоки грузить лениво. Длинные списки не монтировать целиком без пагинации.
