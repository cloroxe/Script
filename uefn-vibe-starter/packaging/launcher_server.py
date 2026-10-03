import multiprocessing
import os
import sys

from uefn_vibe.server import main

if __name__ == "__main__":
    multiprocessing.freeze_support()  # exigé par PyInstaller pour les exe figés
    try:
        main()
    finally:
        # Le transport stdio du MCP ferme stdout à l'arrêt ; le bootloader PyInstaller tente ensuite
        # de vider sys.stdout ET sys.__stdout__ et afficherait « ValueError: I/O operation on closed file ».
        try:
            sys.stdout = sys.__stdout__ = open(os.devnull, "w")
        except OSError:
            pass
