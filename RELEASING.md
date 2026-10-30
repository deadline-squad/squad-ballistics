# Выпуск обновления / Releasing

Программа работает только в Linux и запускается из исходников, поэтому
выпуск — это тег на коммите в **main**: собирать и выкладывать файлы не нужно.
Пользователи обновляются через `git pull` и
`.venv/bin/pip install -r requirements.txt` (см. README).

Релизы выходят в **deadline-squad/squad-ballistics** (remote `deadline`,
`git@github.com:deadline-squad/squad-ballistics.git`; если его нет:
`git remote add deadline git@github.com:deadline-squad/squad-ballistics.git`).
Старый публичный репозиторий DelineDelorian/Squad-Ballistics (remote `origin`)
не трогать: туда не пушить и релизы там не создавать.

## Публикация новой версии

1. Поднять `APP_VERSION` в `config.py`, например `1.6.0`.
2. Добавить запись в начало `RELEASE_NOTES.md` (по-русски и по-английски) —
   это текст релиза на GitHub. Запись описывает изменения с **последнего
   выпущенного** релиза (последнего тега `v*`), а не с версии, которая
   так и не вышла.
3. Закоммитить в рабочую ветку, влить её в **dev**, дождаться зелёного
   **tests** в Actions.
4. Влить **dev** в **main**, поставить тег на этом коммите и запушить их
   в deadline-squad/squad-ballistics:
   ```
   git tag v1.6.0
   git push deadline main v1.6.0
   ```
5. Создать релиз из тега с текстом новой записи `RELEASE_NOTES.md`:
   ```
   gh release create v1.6.0 -R deadline-squad/squad-ballistics \
       --title "Squad Ballistics 1.6.0" --notes-file <запись>
   ```

---

The app is Linux-only and runs from source, so a release is a tag on a commit
in **main**: nothing is built or uploaded. Users update with `git pull` and
`.venv/bin/pip install -r requirements.txt` (see the README).

Releases go to **deadline-squad/squad-ballistics** (remote `deadline`,
`git@github.com:deadline-squad/squad-ballistics.git`; add it with
`git remote add deadline git@github.com:deadline-squad/squad-ballistics.git`
if it is missing). Leave the old public repository
DelineDelorian/Squad-Ballistics (remote `origin`) alone: do not push to it or
create releases there.

1. Bump `APP_VERSION` in `config.py`.
2. Add an entry at the top of `RELEASE_NOTES.md` (Russian and English); it is
   the GitHub release text. The entry describes the changes since the **last
   released** version (the latest `v*` tag), not since a version that was
   never released.
3. Commit on a working branch, merge it into **dev**, wait for a green
   **tests** run.
4. Merge **dev** into **main**, tag that commit and push both to
   deadline-squad/squad-ballistics:
   ```
   git tag v1.6.0
   git push deadline main v1.6.0
   ```
5. Create the GitHub release from the tag with the new notes entry:
   ```
   gh release create v1.6.0 -R deadline-squad/squad-ballistics \
       --title "Squad Ballistics 1.6.0" --notes-file <entry>
   ```
