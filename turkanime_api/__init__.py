from .anime import AnimeSorgula,Anime

def clean_print(string):
    print('\033[2K\033[1G',end="\r")
    print(string,end='\r')
