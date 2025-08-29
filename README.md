# Speakeasy

a toy authentication system that uses voice recognition as 2fa. made for [authly](authly.hackclub.com).

## how it works
you record a voice sample when you sign up or log in. if it matches your initial sample, you are authenticated!

## running
```bash
# clone the repo
$ git clone https://github.com/saturn-vi/voicerec.git
$ cd voicerec

# install dependencies
$ uv venv
$ uv pip install .

# run the server
$ litestar run
```

## tech stack:
- [litestar](https://litestar.dev/) - web framework (also handles sessions and data storage)
- [some random researchers' code](https://arxiv.org/abs/2401.05064) - voice recognition
