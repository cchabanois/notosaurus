FROM python:3.13-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY pyproject.toml .
COPY app app
COPY core/notosaurus_core notosaurus_core
COPY static static

# Not root: its own user, owning the data folder. A new named volume takes this owner;
# one made by an older image (root's) is handed over once with
#   docker run --rm -u 0 -v notosaurus-data:/data notosaurus chown -R notosaurus: /data
# uid 1000: a folder of the computer's (-v ./data:/data) is usually its user's already.
RUN useradd --create-home --uid 1000 notosaurus && mkdir /data && chown notosaurus: /data
USER notosaurus

ENV NOTOSAURUS_DATA=/data
VOLUME /data
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
