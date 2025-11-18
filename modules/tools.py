import io
import os
import re
import edge_tts
import httpx
import logging
from rdkit import Chem
from rdkit.Chem.Draw import rdMolDraw2D
from telegram import Update, InputFile
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)

async def generate_audio(text: str, voice: str) -> bytes | None:
    try:
        clean_text = re.sub(r'[*_`]', '', text)
        temp_file = f"/tmp/tts_{os.urandom(4).hex()}.mp3"
        communicate = edge_tts.Communicate(clean_text, voice)
        await communicate.save(temp_file)
        
        with open(temp_file, 'rb') as f:
            data = f.read()
        os.remove(temp_file)
        return data
    except Exception as e:
        logger.error(f"TTS Error: {e}")
        return None

async def handle_chemistry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    smiles = " ".join(context.args)
    if not smiles:
        await update.message.reply_text("Usage: /chem <SMILES>")
        return
    
    try:
        mol = Chem.MolFromSmiles(smiles)
        if not mol: raise ValueError("Invalid SMILES")
        drawer = rdMolDraw2D.MolDraw2DC(300, 300)
        drawer.DrawMolecule(mol)
        drawer.FinishDrawing()
        png = drawer.GetDrawingText()
        await update.message.reply_photo(io.BytesIO(png), caption=f"Structure: `{smiles}`", parse_mode='Markdown')
    except Exception as e:
        await update.message.reply_text("Could not draw molecule.")

async def handle_latex(update: Update, context: ContextTypes.DEFAULT_TYPE):
    latex = " ".join(context.args)
    if not latex:
        await update.message.reply_text("Usage: /tex <formula>")
        return
    
    url = f"https://latex.codecogs.com/png.latex?%5Cdpi{{300}}%20{httpx.utils.quote(latex)}"
    await update.message.reply_photo(url, caption=f"`{latex}`", parse_mode='Markdown')
