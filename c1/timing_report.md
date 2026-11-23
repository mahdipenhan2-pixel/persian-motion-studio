## Stage 2 timing report - WARN

- c1a: WARN
- c1b: OK
- c1c: OK
- c1d: OK
- s1: WARN
- c1s: OK
- c1e: WARN
- c1f: WARN
- s3: OK
- c1g: OK
- s4: OK
- c1h: OK
- c1h2: WARN
- c1i: OK
- c1j: WARN
- c1k: OK

### c1a - WARN (match 1.00)

- first word vs measured speech onset: -30 ms; last word vs speech end: -390 ms
- first/last word is still >300 ms away from the measured speech edge

| # | script word | recognized | start s | end s | status | timing quality | note |
|---|---|---|---|---|---|---|---|
| 0 | What | What | 5.25 | 5.47 | exact | exact | exact normalized token match; Whisper word timestamp; start moved to the measured speech onset (Whisper was 280 ms early) |
| 1 | if | if | 5.47 | 5.69 | exact | exact | exact normalized token match; Whisper word timestamp |
| 2 | you | you | 5.69 | 5.83 | exact | exact | exact normalized token match; Whisper word timestamp |
| 3 | were | were | 5.83 | 5.93 | exact | exact | exact normalized token match; Whisper word timestamp |
| 4 | born | born | 5.93 | 6.29 | exact | exact | exact normalized token match; Whisper word timestamp |
| 5 | as | as | 6.29 | 6.61 | exact | exact | exact normalized token match; Whisper word timestamp |
| 6 | Kim | Kim | 6.61 | 6.91 | exact | exact | exact normalized token match; Whisper word timestamp |
| 7 | Kardashian? | Kardashian? | 6.91 | 7.27 | exact | exact | exact normalized token match; Whisper word timestamp |

### c1b - OK (match 1.00)

- first word vs measured speech onset: -30 ms; last word vs speech end: -250 ms

| # | script word | recognized | start s | end s | status | timing quality | note |
|---|---|---|---|---|---|---|---|
| 0 | How | How | 8.59 | 8.83 | exact | exact | exact normalized token match; Whisper word timestamp; start moved to the measured speech onset (Whisper was 200 ms early) |
| 1 | would | would | 8.83 | 9.03 | exact | exact | exact normalized token match; Whisper word timestamp |
| 2 | your | your | 9.03 | 9.25 | exact | exact | exact normalized token match; Whisper word timestamp |
| 3 | life | life | 9.25 | 9.61 | exact | exact | exact normalized token match; Whisper word timestamp |
| 4 | unfold? | unfold? | 9.61 | 10.07 | exact | exact | exact normalized token match; Whisper word timestamp |

### c1c - OK (match 1.00)

- first word vs measured speech onset: -30 ms; last word vs speech end: -30 ms

| # | script word | recognized | start s | end s | status | timing quality | note |
|---|---|---|---|---|---|---|---|
| 0 | A | A | 11.31 | 11.41 | exact | exact | exact normalized token match; Whisper word timestamp; start moved to the measured speech onset (Whisper was 300 ms early) |
| 1 | famous | famous | 11.41 | 11.77 | exact | exact | exact normalized token match; Whisper word timestamp |
| 2 | family. | family, | 11.77 | 12.33 | exact | exact | exact normalized token match; Whisper word timestamp |
| 3 | Television | television | 12.67 | 13.05 | exact | exact | exact normalized token match; Whisper word timestamp |
| 4 | cameras. | cameras, | 13.05 | 13.63 | exact | exact | exact normalized token match; Whisper word timestamp |
| 5 | Fashion, | fashion, | 14.07 | 14.57 | exact | exact | exact normalized token match; Whisper word timestamp |
| 6 | fame, | fame, | 14.97 | 15.35 | exact | exact | exact normalized token match; Whisper word timestamp |
| 7 | and | and | 15.81 | 15.91 | exact | exact | exact normalized token match; Whisper word timestamp |
| 8 | a | a | 15.91 | 16.01 | exact | exact | exact normalized token match; Whisper word timestamp |
| 9 | business | business | 16.01 | 16.37 | exact | exact | exact normalized token match; Whisper word timestamp |
| 10 | empire. | empire. | 16.37 | 16.87 | exact | exact | exact normalized token match; Whisper word timestamp |

### c1d - OK (match 1.00)

- first word vs measured speech onset: -30 ms; last word vs speech end: -240 ms

| # | script word | recognized | start s | end s | status | timing quality | note |
|---|---|---|---|---|---|---|---|
| 0 | But | But, | 17.86 | 18.03 | exact | exact | exact normalized token match; Whisper word timestamp; start moved to the measured speech onset (Whisper was 270 ms early) |
| 1 | none | none | 18.11 | 18.35 | exact | exact | exact normalized token match; Whisper word timestamp |
| 2 | of | of | 18.35 | 18.53 | exact | exact | exact normalized token match; Whisper word timestamp |
| 3 | that | that | 18.53 | 18.69 | exact | exact | exact normalized token match; Whisper word timestamp |
| 4 | exists | exists | 18.69 | 18.97 | exact | exact | exact normalized token match; Whisper word timestamp |
| 5 | yet. | yet. | 18.97 | 19.37 | exact | exact | exact normalized token match; Whisper word timestamp |
| 6 | Your | Your | 19.95 | 20.13 | exact | exact | exact normalized token match; Whisper word timestamp |
| 7 | story | story | 20.13 | 20.51 | exact | exact | exact normalized token match; Whisper word timestamp |
| 8 | begins | begins | 20.51 | 21.03 | exact | exact | exact normalized token match; Whisper word timestamp |
| 9 | in | in | 21.03 | 21.35 | exact | exact | exact normalized token match; Whisper word timestamp |
| 10 | Los | Los | 21.35 | 21.51 | exact | exact | exact normalized token match; Whisper word timestamp |
| 11 | Angeles. | Angeles. | 21.51 | 21.93 | exact | exact | exact normalized token match; Whisper word timestamp |

### s1 - WARN (match 1.00)

- 1 word(s) aligned with differences or estimated boundaries
- first word vs measured speech onset: -30 ms; last word vs speech end: -140 ms

| # | script word | recognized | start s | end s | status | timing quality | note |
|---|---|---|---|---|---|---|---|
| 0 | You | You | 23.06 | 23.23 | exact | exact | exact normalized token match; Whisper word timestamp; start moved to the measured speech onset (Whisper was 290 ms early) |
| 1 | are | were | 23.28 | 23.33 | aligned | estimated | ESTIMATED boundary from matched character positions; review audio |
| 2 | born | born | 23.33 | 23.65 | exact | exact | exact normalized token match; Whisper word timestamp |
| 3 | in | in | 23.65 | 23.91 | exact | exact | exact normalized token match; Whisper word timestamp |
| 4 | Los | Los | 23.91 | 24.11 | exact | exact | exact normalized token match; Whisper word timestamp |
| 5 | Angeles | Angeles | 24.11 | 24.63 | exact | exact | exact normalized token match; Whisper word timestamp |
| 6 | on | on | 24.63 | 25.01 | exact | exact | exact normalized token match; Whisper word timestamp |
| 7 | October | October | 25.01 | 25.25 | exact | exact | exact normalized token match; Whisper word timestamp |
| 8 | 21st, | 21st, | 25.25 | 26.29 | exact | exact | exact normalized token match; Whisper word timestamp |
| 9 | 1980. | 1980. | 26.37 | 27.11 | exact | exact | exact normalized token match; Whisper word timestamp |

### c1s - OK (match 1.00)

- first word vs measured speech onset: -30 ms; last word vs speech end: -50 ms

| # | script word | recognized | start s | end s | status | timing quality | note |
|---|---|---|---|---|---|---|---|
| 0 | Your | Your | 28.22 | 28.43 | exact | exact | exact normalized token match; Whisper word timestamp; start moved to the measured speech onset (Whisper was 270 ms early) |
| 1 | world | World | 28.43 | 28.81 | exact | exact | exact normalized token match; Whisper word timestamp |
| 2 | is | is | 28.81 | 29.11 | exact | exact | exact normalized token match; Whisper word timestamp |
| 3 | the | the | 29.11 | 29.25 | exact | exact | exact normalized token match; Whisper word timestamp |
| 4 | Los | Los | 29.25 | 29.43 | exact | exact | exact normalized token match; Whisper word timestamp |
| 5 | Angeles | Angeles | 29.43 | 29.85 | exact | exact | exact normalized token match; Whisper word timestamp |
| 6 | of | of | 29.85 | 30.17 | exact | exact | exact normalized token match; Whisper word timestamp |
| 7 | 1980: | 1980, | 30.17 | 30.85 | exact | exact | exact normalized token match; Whisper word timestamp |
| 8 | palm | palm | 31.27 | 31.55 | exact | exact | exact normalized token match; Whisper word timestamp |
| 9 | trees, | trees, | 31.55 | 31.93 | exact | exact | exact normalized token match; Whisper word timestamp |
| 10 | film | film | 32.31 | 32.63 | exact | exact | exact normalized token match; Whisper word timestamp |
| 11 | studios, | studios, | 32.63 | 33.09 | exact | exact | exact normalized token match; Whisper word timestamp |
| 12 | and | and | 33.57 | 33.73 | exact | exact | exact normalized token match; Whisper word timestamp |
| 13 | a | a | 33.73 | 33.85 | exact | exact | exact normalized token match; Whisper word timestamp |
| 14 | city | city | 33.85 | 34.09 | exact | exact | exact normalized token match; Whisper word timestamp |
| 15 | built | built | 34.09 | 34.47 | exact | exact | exact normalized token match; Whisper word timestamp |
| 16 | on | on | 34.47 | 34.77 | exact | exact | exact normalized token match; Whisper word timestamp |
| 17 | fame. | fame. | 34.77 | 35.09 | exact | exact | exact normalized token match; Whisper word timestamp |

### c1e - WARN (match 1.00)

- 1 word(s) aligned with differences or estimated boundaries
- first word vs measured speech onset: -30 ms; last word vs speech end: -130 ms

| # | script word | recognized | start s | end s | status | timing quality | note |
|---|---|---|---|---|---|---|---|
| 0 | Your | Your | 35.99 | 36.13 | exact | exact | exact normalized token match; Whisper word timestamp; start moved to the measured speech onset (Whisper was 220 ms early) |
| 1 | father, | father, | 36.13 | 36.49 | exact | exact | exact normalized token match; Whisper word timestamp |
| 2 | Robert, | Robert, | 36.79 | 37.11 | exact | exact | exact normalized token match; Whisper word timestamp |
| 3 | is | is | 37.45 | 37.57 | exact | exact | exact normalized token match; Whisper word timestamp |
| 4 | a | a | 37.57 | 37.67 | exact | exact | exact normalized token match; Whisper word timestamp |
| 5 | lawyer. | lawyer. | 37.67 | 37.91 | exact | exact | exact normalized token match; Whisper word timestamp |
| 6 | Your | Your | 38.53 | 38.61 | exact | exact | exact normalized token match; Whisper word timestamp |
| 7 | mother, | mother, | 38.61 | 38.83 | exact | exact | exact normalized token match; Whisper word timestamp |
| 8 | Kris, | Chris, | 39.074 | 39.17 | aligned | estimated | ESTIMATED boundary from matched character positions; review audio |
| 9 | is | is | 39.57 | 39.71 | exact | exact | exact normalized token match; Whisper word timestamp |
| 10 | raising | raising | 39.71 | 40.05 | exact | exact | exact normalized token match; Whisper word timestamp |
| 11 | a | a | 40.05 | 40.25 | exact | exact | exact normalized token match; Whisper word timestamp |
| 12 | growing | growing | 40.25 | 40.57 | exact | exact | exact normalized token match; Whisper word timestamp |
| 13 | family. | family. | 40.57 | 41.07 | exact | exact | exact normalized token match; Whisper word timestamp |

### c1f - WARN (match 1.00)

- 2 word(s) aligned with differences or estimated boundaries
- first word vs measured speech onset: -30 ms; last word vs speech end: -100 ms

| # | script word | recognized | start s | end s | status | timing quality | note |
|---|---|---|---|---|---|---|---|
| 0 | You | You | 42.15 | 42.31 | exact | exact | exact normalized token match; Whisper word timestamp; start moved to the measured speech onset (Whisper was 280 ms early) |
| 1 | grow | grow | 42.31 | 42.57 | exact | exact | exact normalized token match; Whisper word timestamp |
| 2 | up | up | 42.57 | 42.83 | exact | exact | exact normalized token match; Whisper word timestamp |
| 3 | beside | beside | 42.83 | 43.25 | exact | exact | exact normalized token match; Whisper word timestamp |
| 4 | your | your | 43.25 | 43.51 | exact | exact | exact normalized token match; Whisper word timestamp |
| 5 | older | older | 43.51 | 43.77 | exact | exact | exact normalized token match; Whisper word timestamp |
| 6 | sister, | sister, | 43.77 | 44.17 | exact | exact | exact normalized token match; Whisper word timestamp |
| 7 | Kourtney. | Courtney. | 44.45 | 44.73 | aligned | estimated | ESTIMATED boundary from matched character positions; review audio |
| 8 | Later | Later | 45.27 | 45.45 | exact | exact | exact normalized token match; Whisper word timestamp |
| 9 | come | come | 45.45 | 45.75 | exact | exact | exact normalized token match; Whisper word timestamp |
| 10 | a | a | 45.75 | 45.87 | exact | exact | exact normalized token match; Whisper word timestamp |
| 11 | sister, | sister, | 45.87 | 46.15 | exact | exact | exact normalized token match; Whisper word timestamp |
| 12 | Khloé, | Chloe, | 46.374 | 46.506 | aligned | estimated | ESTIMATED boundary from matched character positions; review audio |
| 13 | and | and | 46.91 | 47.01 | exact | exact | exact normalized token match; Whisper word timestamp |
| 14 | a | a | 47.01 | 47.11 | exact | exact | exact normalized token match; Whisper word timestamp |
| 15 | brother, | brother, | 47.11 | 47.31 | exact | exact | exact normalized token match; Whisper word timestamp |
| 16 | Rob. | Rob. | 47.61 | 47.83 | exact | exact | exact normalized token match; Whisper word timestamp |

### s3 - OK (match 1.00)

- first word vs measured speech onset: -30 ms; last word vs speech end: -170 ms

| # | script word | recognized | start s | end s | status | timing quality | note |
|---|---|---|---|---|---|---|---|
| 0 | When | When | 48.86 | 49.05 | exact | exact | exact normalized token match; Whisper word timestamp; start moved to the measured speech onset (Whisper was 290 ms early) |
| 1 | you | you | 49.05 | 49.25 | exact | exact | exact normalized token match; Whisper word timestamp |
| 2 | are | are | 49.25 | 49.35 | exact | exact | exact normalized token match; Whisper word timestamp |
| 3 | nine, | nine, | 49.35 | 49.63 | exact | exact | exact normalized token match; Whisper word timestamp |
| 4 | your | your | 50.03 | 50.15 | exact | exact | exact normalized token match; Whisper word timestamp |
| 5 | parents | parents | 50.15 | 50.55 | exact | exact | exact normalized token match; Whisper word timestamp |
| 6 | separate. | separate. | 50.55 | 51.03 | exact | exact | exact normalized token match; Whisper word timestamp |

### c1g - OK (match 1.00)

- first word vs measured speech onset: -30 ms; last word vs speech end: -200 ms

| # | script word | recognized | start s | end s | status | timing quality | note |
|---|---|---|---|---|---|---|---|
| 0 | It | It | 52.02 | 52.13 | exact | exact | exact normalized token match; Whisper word timestamp; start moved to the measured speech onset (Whisper was 270 ms early) |
| 1 | is | is | 52.13 | 52.29 | exact | exact | exact normalized token match; Whisper word timestamp |
| 2 | 1989, | 1989 | 52.29 | 53.09 | exact | exact | exact normalized token match; Whisper word timestamp |
| 3 | and | and | 53.09 | 54.03 | exact | exact | exact normalized token match; Whisper word timestamp |
| 4 | the | the | 54.03 | 54.15 | exact | exact | exact normalized token match; Whisper word timestamp |
| 5 | home | home | 54.15 | 54.43 | exact | exact | exact normalized token match; Whisper word timestamp |
| 6 | you | you | 54.43 | 54.65 | exact | exact | exact normalized token match; Whisper word timestamp |
| 7 | know | know | 54.65 | 54.87 | exact | exact | exact normalized token match; Whisper word timestamp |
| 8 | is | is | 54.87 | 55.27 | exact | exact | exact normalized token match; Whisper word timestamp |
| 9 | about | about | 55.27 | 55.55 | exact | exact | exact normalized token match; Whisper word timestamp |
| 10 | to | to | 55.55 | 55.79 | exact | exact | exact normalized token match; Whisper word timestamp |
| 11 | change. | change. | 55.79 | 56.11 | exact | exact | exact normalized token match; Whisper word timestamp |

### s4 - OK (match 1.00)

- first word vs measured speech onset: -30 ms; last word vs speech end: 30 ms

| # | script word | recognized | start s | end s | status | timing quality | note |
|---|---|---|---|---|---|---|---|
| 0 | Two | Two | 57.14 | 57.29 | exact | exact | exact normalized token match; Whisper word timestamp; start moved to the measured speech onset (Whisper was 250 ms early) |
| 1 | years | years | 57.29 | 57.51 | exact | exact | exact normalized token match; Whisper word timestamp |
| 2 | later, | later, | 57.51 | 57.89 | exact | exact | exact normalized token match; Whisper word timestamp |
| 3 | your | your | 58.23 | 58.33 | exact | exact | exact normalized token match; Whisper word timestamp |
| 4 | mother | mother | 58.33 | 58.61 | exact | exact | exact normalized token match; Whisper word timestamp |
| 5 | marries | marries | 58.61 | 59.07 | exact | exact | exact normalized token match; Whisper word timestamp |
| 6 | Olympic | Olympic | 59.07 | 59.49 | exact | exact | exact normalized token match; Whisper word timestamp |
| 7 | champion | champion, | 59.49 | 60.07 | exact | exact | exact normalized token match; Whisper word timestamp |
| 8 | Bruce | Bruce | 60.35 | 60.51 | exact | exact | exact normalized token match; Whisper word timestamp |
| 9 | Jenner. | Jenner. | 60.51 | 60.99 | exact | exact | exact normalized token match; Whisper word timestamp |

### c1h - OK (match 1.00)

- first word vs measured speech onset: -30 ms; last word vs speech end: -20 ms

| # | script word | recognized | start s | end s | status | timing quality | note |
|---|---|---|---|---|---|---|---|
| 0 | She | She | 61.85 | 62.01 | exact | exact | exact normalized token match; Whisper word timestamp; start moved to the measured speech onset (Whisper was 260 ms early) |
| 1 | marries | marries | 62.01 | 62.49 | exact | exact | exact normalized token match; Whisper word timestamp |
| 2 | him | him | 62.49 | 62.63 | exact | exact | exact normalized token match; Whisper word timestamp |
| 3 | in | in | 62.63 | 62.81 | exact | exact | exact normalized token match; Whisper word timestamp |
| 4 | April | April | 62.81 | 63.13 | exact | exact | exact normalized token match; Whisper word timestamp |
| 5 | 1991, | 1991, | 63.13 | 64.01 | exact | exact | exact normalized token match; Whisper word timestamp |
| 6 | one | one | 64.49 | 64.75 | exact | exact | exact normalized token match; Whisper word timestamp |
| 7 | month | month | 64.75 | 65.09 | exact | exact | exact normalized token match; Whisper word timestamp |
| 8 | after | after | 65.09 | 65.41 | exact | exact | exact normalized token match; Whisper word timestamp |
| 9 | her | her | 65.41 | 65.57 | exact | exact | exact normalized token match; Whisper word timestamp |
| 10 | divorce | divorce | 65.57 | 66.03 | exact | exact | exact normalized token match; Whisper word timestamp |
| 11 | is | is | 66.03 | 66.23 | exact | exact | exact normalized token match; Whisper word timestamp |
| 12 | final. | final. | 66.23 | 66.59 | exact | exact | exact normalized token match; Whisper word timestamp |

### c1h2 - WARN (match 1.00)

- first word vs measured speech onset: -30 ms; last word vs speech end: -360 ms
- first/last word is still >300 ms away from the measured speech edge

| # | script word | recognized | start s | end s | status | timing quality | note |
|---|---|---|---|---|---|---|---|
| 0 | Their | Their | 67.66 | 67.85 | exact | exact | exact normalized token match; Whisper word timestamp; start moved to the measured speech onset (Whisper was 290 ms early) |
| 1 | marriage | marriage | 67.85 | 68.27 | exact | exact | exact normalized token match; Whisper word timestamp |
| 2 | will | will | 68.27 | 68.49 | exact | exact | exact normalized token match; Whisper word timestamp |
| 3 | last | last | 68.49 | 68.89 | exact | exact | exact normalized token match; Whisper word timestamp |
| 4 | until | until | 68.89 | 69.27 | exact | exact | exact normalized token match; Whisper word timestamp |
| 5 | 2014. | 2014. | 69.27 | 70.37 | exact | exact | exact normalized token match; Whisper word timestamp |

### c1i - OK (match 1.00)

- first word vs measured speech onset: -30 ms; last word vs speech end: 0 ms

| # | script word | recognized | start s | end s | status | timing quality | note |
|---|---|---|---|---|---|---|---|
| 0 | On | On | 71.56 | 71.69 | exact | exact | exact normalized token match; Whisper word timestamp; start moved to the measured speech onset (Whisper was 290 ms early) |
| 1 | July | July | 71.69 | 71.93 | exact | exact | exact normalized token match; Whisper word timestamp |
| 2 | 30th, | 30th, | 71.93 | 72.75 | exact | exact | exact normalized token match; Whisper word timestamp |
| 3 | 1976, | 1976 | 72.89 | 73.61 | exact | exact | exact normalized token match; Whisper word timestamp |
| 4 | in | in | 73.61 | 74.23 | exact | exact | exact normalized token match; Whisper word timestamp |
| 5 | Montreal, | Montreal, | 74.23 | 74.61 | exact | exact | exact normalized token match; Whisper word timestamp |
| 6 | Bruce | Bruce | 75.27 | 75.53 | exact | exact | exact normalized token match; Whisper word timestamp |
| 7 | won | won | 75.53 | 75.97 | exact | exact | exact normalized token match; Whisper word timestamp |
| 8 | the | the | 75.97 | 76.21 | exact | exact | exact normalized token match; Whisper word timestamp |
| 9 | Olympic | Olympic | 76.21 | 76.65 | exact | exact | exact normalized token match; Whisper word timestamp |
| 10 | decathlon | Decathlon | 76.65 | 77.35 | exact | exact | exact normalized token match; Whisper word timestamp |
| 11 | and | and | 77.35 | 78.05 | exact | exact | exact normalized token match; Whisper word timestamp |
| 12 | set | set | 78.05 | 78.59 | exact | exact | exact normalized token match; Whisper word timestamp |
| 13 | a | a | 78.59 | 78.87 | exact | exact | exact normalized token match; Whisper word timestamp |
| 14 | world | world | 78.87 | 79.15 | exact | exact | exact normalized token match; Whisper word timestamp |
| 15 | record. | record. | 79.15 | 79.59 | exact | exact | exact normalized token match; Whisper word timestamp |

### c1j - WARN (match 0.94)

- 1 word(s) could not be matched and remain unhighlighted
- first word vs measured speech onset: -30 ms; last word vs speech end: -110 ms

| # | script word | recognized | start s | end s | status | timing quality | note |
|---|---|---|---|---|---|---|---|
| 0 | The | The | 80.51 | 80.65 | exact | exact | exact normalized token match; Whisper word timestamp; start moved to the measured speech onset (Whisper was 260 ms early) |
| 1 | decathlon | Decathlon | 80.65 | 81.19 | exact | exact | exact normalized token match; Whisper word timestamp |
| 2 | has | has | 81.19 | 81.63 | exact | exact | exact normalized token match; Whisper word timestamp |
| 3 | ten |  | - | - | unmatched | unresolved | UNRESOLVED: no reliable Whisper token matched this script word |
| 4 | events | events | 81.99 | 82.49 | exact | exact | exact normalized token match; Whisper word timestamp |
| 5 | over | over | 82.49 | 82.81 | exact | exact | exact normalized token match; Whisper word timestamp |
| 6 | two | two | 82.81 | 83.13 | exact | exact | exact normalized token match; Whisper word timestamp |
| 7 | days, | days, | 83.13 | 83.41 | exact | exact | exact normalized token match; Whisper word timestamp |
| 8 | and | and | 83.91 | 83.99 | exact | exact | exact normalized token match; Whisper word timestamp |
| 9 | its | its | 83.99 | 84.11 | exact | exact | exact normalized token match; Whisper word timestamp |
| 10 | winner | winner | 84.11 | 84.39 | exact | exact | exact normalized token match; Whisper word timestamp |
| 11 | is | is | 84.39 | 84.63 | exact | exact | exact normalized token match; Whisper word timestamp |
| 12 | often | often | 84.63 | 84.91 | exact | exact | exact normalized token match; Whisper word timestamp |
| 13 | called | called | 84.91 | 85.23 | exact | exact | exact normalized token match; Whisper word timestamp |
| 14 | the | the | 85.23 | 85.43 | exact | exact | exact normalized token match; Whisper word timestamp |
| 15 | world's | world's | 85.43 | 85.95 | exact | exact | exact normalized token match; Whisper word timestamp |
| 16 | greatest | greatest | 85.95 | 86.25 | exact | exact | exact normalized token match; Whisper word timestamp |
| 17 | athlete. | athlete. | 86.25 | 86.81 | exact | exact | exact normalized token match; Whisper word timestamp |

### c1k - OK (match 1.00)

- first word vs measured speech onset: -30 ms; last word vs speech end: -30 ms

| # | script word | recognized | start s | end s | status | timing quality | note |
|---|---|---|---|---|---|---|---|
| 0 | Now | Now | 87.73 | 87.99 | exact | exact | exact normalized token match; Whisper word timestamp; start moved to the measured speech onset (Whisper was 220 ms early) |
| 1 | that | that | 87.99 | 88.27 | exact | exact | exact normalized token match; Whisper word timestamp |
| 2 | name | name | 88.27 | 88.57 | exact | exact | exact normalized token match; Whisper word timestamp |
| 3 | is | is | 88.57 | 88.85 | exact | exact | exact normalized token match; Whisper word timestamp |
| 4 | part | part | 88.85 | 89.09 | exact | exact | exact normalized token match; Whisper word timestamp |
| 5 | of | of | 89.09 | 89.23 | exact | exact | exact normalized token match; Whisper word timestamp |
| 6 | your | your | 89.23 | 89.35 | exact | exact | exact normalized token match; Whisper word timestamp |
| 7 | family, | family, | 89.35 | 89.77 | exact | exact | exact normalized token match; Whisper word timestamp |
| 8 | and | and | 89.97 | 90.31 | exact | exact | exact normalized token match; Whisper word timestamp |
| 9 | Los | Los | 90.31 | 90.51 | exact | exact | exact normalized token match; Whisper word timestamp |
| 10 | Angeles | Angeles | 90.51 | 90.95 | exact | exact | exact normalized token match; Whisper word timestamp |
| 11 | is | is | 90.95 | 91.35 | exact | exact | exact normalized token match; Whisper word timestamp |
| 12 | about | about | 91.35 | 91.55 | exact | exact | exact normalized token match; Whisper word timestamp |
| 13 | to | to | 91.55 | 91.75 | exact | exact | exact normalized token match; Whisper word timestamp |
| 14 | turn | turn | 91.75 | 91.95 | exact | exact | exact normalized token match; Whisper word timestamp |
| 15 | your | your | 91.95 | 92.13 | exact | exact | exact normalized token match; Whisper word timestamp |
| 16 | father | father | 92.13 | 92.51 | exact | exact | exact normalized token match; Whisper word timestamp |
| 17 | into | into | 92.51 | 93.13 | exact | exact | exact normalized token match; Whisper word timestamp |
| 18 | a | a | 93.13 | 93.29 | exact | exact | exact normalized token match; Whisper word timestamp |
| 19 | public | public | 93.29 | 93.69 | exact | exact | exact normalized token match; Whisper word timestamp |
| 20 | figure. | figure. | 93.69 | 94.09 | exact | exact | exact normalized token match; Whisper word timestamp |

