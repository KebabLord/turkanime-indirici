from .anime import animeSorgula,animeIndir,animeOynat

def cleanPrint(string):
    print('\033[2K\033[1G',end="\r")
    print(string,end='\r')
