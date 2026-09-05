# NOTICE

CourDL is a desktop GUI and wrapper around existing tools.

## dl_coursera

Download engine: [FLZ101/dl_coursera](https://github.com/FLZ101/dl_coursera) 1.0.1.
CourDL does not reimplement Coursera's crawler. Pin bumps belong in `engine/pyproject.toml`.

## Bāke Studio / Pake

The desktop shell layout (init overlay, first-run wizard, form, live log) is modeled on
[lumotic-ca/bake-studio](https://github.com/lumotic-ca/bake-studio), which is based on
[Pake](https://github.com/tw93/Pake) by tw93. CourDL does not bundle Bake CLI, Node, or Pake.

## Coursera

Use CourDL only for content you are enrolled to access. Session cookies are equivalent to
being logged in. Do not commit `cookies.txt`.
