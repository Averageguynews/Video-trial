# FAFO News: Michael Carrick sacked

`carrick-sacked.mp4` is a 1080x1920, 31 s video in the same FAFO News layout as the earlier rugby episode.

- **Intro (0-6.4 s):** set to Steam's "Na Na Hey Hey Kiss Him Goodbye". It cuts through three photos on the chant: hand over face, then clapping, then the SACKED poster on "hey hey hey... goodbye". A flash leads into the studio.
- **Body:** the three takes (IMG_6998, IMG_6999, IMG_7002) with word-by-word captions. The photo panel pans across the three Carrick photos. The song keeps playing quietly underneath.

## Re-render

    python3 render.py --takes IMG_6998.mov IMG_6999.mov IMG_7002.mov \
      --photos photo-clap.jpg photo-nose.jpg photo-sacked.jpg \
      --music steam-clip.mp4 --music-start 3.4 --bed 0.2 \
      --fonts FONT_DIR --out carrick-sacked.mp4

- `--music-start` is the second in the song file where the intro starts.
- `--bed` sets how loud the song is under the talking (0.2 by default).
- The song file is not in the repo.

Fonts: Anton and Montserrat, from the npm packages `@fontsource/anton` and `@fontsource/montserrat`.
