# SSL Certificates Directory

This directory should contain your SSL/TLS certificates for HTTPS.

## For Production

Place your SSL certificates here:
- `cert.pem` - SSL certificate (or `fullchain.pem` for Let's Encrypt)
- `key.pem` - Private key (or `privkey.pem` for Let's Encrypt)
- `chain.pem` - Certificate chain (optional, for Let's Encrypt)

## Generating Self-Signed Certificates (Development Only)

For local development/testing, generate a self-signed certificate:

```bash
cd nginx/ssl
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
    -keyout key.pem \
    -out cert.pem \
    -subj "/C=US/ST=State/L=City/O=Organization/CN=localhost"
```

**WARNING**: Never use self-signed certificates in production!

## Let's Encrypt (Production Recommended)

For production, use Let's Encrypt for free, trusted SSL certificates:

```bash
# Install certbot
sudo apt-get install certbot

# Generate certificate (manual mode for Docker)
sudo certbot certonly --manual --preferred-challenges dns -d yourdomain.com

# Copy certificates to this directory
sudo cp /etc/letsencrypt/live/yourdomain.com/fullchain.pem ./cert.pem
sudo cp /etc/letsencrypt/live/yourdomain.com/privkey.pem ./key.pem
```

## Certificate Renewal

Let's Encrypt certificates expire after 90 days. Set up auto-renewal:

```bash
# Add to crontab
0 0 1 * * certbot renew --quiet && docker-compose -f docker-compose.prod.yml restart nginx
```

## File Permissions

Ensure certificates have proper permissions:

```bash
chmod 644 cert.pem
chmod 600 key.pem
```

## Security

- Never commit SSL private keys to Git
- Use `.gitignore` to exclude `*.pem`, `*.key`, `*.crt`
- Rotate certificates before expiry
- Use strong ciphers (configured in nginx.conf)
