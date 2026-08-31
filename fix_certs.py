# fix_certs.py — превращает скачанные .cer (возможно, DER или битый PEM) в чистый PEM
import base64
import pathlib

for f in pathlib.Path('certs').glob('*.cer'):
    data = f.read_bytes()
    text = data.decode('latin-1')

    if '-----BEGIN CERTIFICATE-----' in text:
        # между заголовком и концом: либо base64, либо бинарный DER
        body = text.split('-----BEGIN CERTIFICATE-----', 1)[1]
        body = body.split('-----END CERTIFICATE-----', 1)[0]
        clean = ''.join(body.split())
        try:
            der = base64.b64decode(clean, validate=True)
        except Exception:
            # бинарный payload: берём сырые байты между строками заголовка
            for sep_beg, sep_end in ((b'-----BEGIN CERTIFICATE-----\r\n', b'\r\n-----END'),
                                     (b'-----BEGIN CERTIFICATE-----\n', b'\n-----END')):
                if sep_beg in data:
                    der = data.split(sep_beg, 1)[1].split(sep_end, 1)[0]
                    break
            else:
                print(f'{f}: НЕ ПОЛУЧИЛОСЬ извлечь — покажите файл мне')
                continue
    else:
        der = data  # чистый DER без заголовков

    b64 = base64.b64encode(der).decode()
    pem = ('-----BEGIN CERTIFICATE-----\n'
           + '\n'.join(b64[i:i+64] for i in range(0, len(b64), 64))
           + '\n-----END CERTIFICATE-----\n')
    out = f.with_suffix('.pem')
    out.write_text(pem, encoding='ascii')
    print(f'{f.name} -> {out.name}  ({len(der)} bytes)')
