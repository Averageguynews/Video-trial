# FAFO News: Michael Carrick sacked

`carrick-sacked.mp4` is a 1080x1920, 28 s video in the same FAFO News layout as the earlier rugby episode.

- **Intro (0–3 s):** the Carrick "sacked" graphic with a BREAKING / FAFO NEWS slam, then a flash into the studio layout.
- **Body:** the three takes (IMG_6998, IMG_6999, IMG_7002) in order, with word-by-word captions. The photo panel pans across the Carrick graphic.
- **Music:** a short generated news sting is used as a placeholder (see below).

## Adding the Steam track
To add your own licensed copy of "Na Na Hey Hey Kiss Him Goodbye", re-render with:

    python3 render.py --takes IMG_6998.mov IMG_6999.mov IMG_7002.mov \
      --photo carrick-photo.jpg --fonts FONT_DIR --out carrick-sacked.mp4 \
      --music steam.mp3 --music-start 0

Set `--music-start` to the second where the chorus begins. The song plays full volume over the intro and is turned down under the talking.

Fonts: Anton and Montserrat, from the npm packages `@fontsource/anton` and `@fontsource/montserrat`.
