# Aktualizacja FIFA Night Flex do v1.3

Z v1.2 podmień:

- `app.py`
- `database.py`
- `logic.py`
- `ui.py`

`requirements.txt` nie wymaga zmian.

## Jedyna nowa konfiguracja

W Streamlit Cloud dodaj do tych samych Secrets, w których masz `DATABASE_URL`:

```toml
ADMIN_PASSWORD = "fifanight"
```

Nie dodawaj prawdziwego hasła do plików na GitHubie.

Po commicie wykonaj `Manage app → Reboot app`, żeby Streamlit na pewno załadował wszystkie cztery nowe moduły.

Neon nie wymaga ręcznego SQL — v1.3 korzysta z istniejących tabel i `app_settings`.
