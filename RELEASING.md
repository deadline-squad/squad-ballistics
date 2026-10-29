# Выпуск обновления / Releasing

Программа работает только в Linux и запускается из исходников, поэтому
выпуск — это тег на коммите в **main**: собирать и выкладывать файлы не нужно.
Пользователи обновляются через `git pull` (и `pip install -r requirements.txt`,
если поменялись зависимости).

## Публикация новой версии

1. Поднять `APP_VERSION` в `config.py`, например `1.6.0`.
2. Добавить запись в начало `RELEASE_NOTES.md` (по-русски и по-английски) —
   это текст релиза на GitHub.
3. Закоммитить в рабочую ветку, влить её в **dev**, дождаться зелёного
   **tests** в Actions.
4. Влить **dev** в **main**, поставить тег на этом коммите и запушить его:
   ```
   git tag v1.6.0
   git push origin main v1.6.0
   ```
5. Создать релиз из тега с текстом новой записи `RELEASE_NOTES.md`:
   ```
   gh release create v1.6.0 --title "Squad Ballistics 1.6.0" --notes-file <запись>
   ```

---

The app is Linux-only and runs from source, so a release is a tag on a commit
in **main**: nothing is built or uploaded. Users update with `git pull` (and
`pip install -r requirements.txt` when the dependencies changed).

1. Bump `APP_VERSION` in `config.py`.
2. Add an entry at the top of `RELEASE_NOTES.md` (Russian and English); it is
   the GitHub release text.
3. Commit on a working branch, merge it into **dev**, wait for a green
   **tests** run.
4. Merge **dev** into **main**, tag that commit and push the tag.
5. Create the GitHub release from the tag with the new notes entry.
