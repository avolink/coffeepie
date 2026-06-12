# Coffee Pie PKI Certificate Lifecycle

Manages certificates for internal L2/L3/L4 network communication between
orchestrator, DC agents, actors, and Sunshine nodes. Currently operates
on IPv4. IPv8 (IETF draft-thain-ipv8-02) Zone Server authentication (OAuth8/JWT)
is on the roadmap as a complementary network-layer identity layer (target: 2035
or RFC maturity).

## Architecture

```
Coffee Pie Internal CA (self-signed, offline root)
  │
  ├── DC Intermediate CA (per datacenter)
  │     ├── orchestrator.coffeepie.lan
  │     ├── dc-agent.dc1.coffeepie.lan
  │     ├── pve-{A..Z}.dc1.coffeepie.lan
  │     └── actor-*.dc1.coffeepie.lan
  │
  └── Client CA (for codec terminals)
        └── terminal-*.coffeepie.lan
```

## Key Generation

```bash
# Generate keys with coffeepie-keygen (tools/security/)
coffeepie-keygen --purpose orchestrator --node-id dc1-orch --out-dir ./certs
coffeepie-keygen --purpose dc-agent --node-id dc1-agent --out-dir ./certs
coffeepie-keygen --ca --out-dir ./certs
```

## Certificate Issuance

### 1. Create Root CA (once, offline)

```bash
openssl genpkey -algorithm Ed25519 -out root-ca.key
openssl req -new -x509 -days 3650 -key root-ca.key -out root-ca.crt \
  -subj "/O=Coffee Pie/CN=Coffee Pie Internal Root CA"
chmod 400 root-ca.key
```

Store `root-ca.key` in an HSM or air-gapped machine. Only `root-ca.crt` is distributed.

### 2. Create Datacenter Intermediate CA

```bash
# Per datacenter
openssl genpkey -algorithm Ed25519 -out dc1-intermediate.key
openssl req -new -key dc1-intermediate.key -out dc1-intermediate.csr \
  -subj "/O=Coffee Pie/CN=DC1 Intermediate CA"

# Sign with root CA (offline)
openssl x509 -req -days 1825 -in dc1-intermediate.csr \
  -CA root-ca.crt -CAkey root-ca.key -CAcreateserial \
  -out dc1-intermediate.crt
```

### 3. Issue Node Certificates

```bash
# Per node
NODE="orchestrator.dc1.coffeepie.lan"

openssl genpkey -algorithm Ed25519 -out ${NODE}.key
openssl req -new -key ${NODE}.key -out ${NODE}.csr \
  -subj "/O=Coffee Pie/CN=${NODE}"

# Sign with DC intermediate CA
openssl x509 -req -days 365 -in ${NODE}.csr \
  -CA dc1-intermediate.crt -CAkey dc1-intermediate.key \
  -out ${NODE}.crt

# Deploy to node
scp ${NODE}.crt ${NODE}.key root@${NODE}:/etc/coffeepie/tls/
ssh root@${NODE} "chmod 600 /etc/coffeepie/tls/*.key"
```

## Certificate Rotation

### Automated Rotation (cron job)

```bash
#!/bin/bash
# /etc/cron.monthly/coffeepie-cert-rotation
# Rotates certificates that expire within 30 days

THRESHOLD_DAYS=30
CERT_DIR="/etc/coffeepie/tls"
CA_DIR="/etc/coffeepie/ca"

for cert in $CERT_DIR/*.crt; do
    EXPIRY=$(openssl x509 -enddate -noout -in "$cert" | cut -d= -f2)
    EXPIRY_EPOCH=$(date -d "$EXPIRY" +%s)
    NOW=$(date +%s)
    DAYS_LEFT=$(( ($EXPIRY_EPOCH - $NOW) / 86400 ))

    if [ $DAYS_LEFT -le $THRESHOLD_DAYS ]; then
        NODE=$(basename "$cert" .crt)
        echo "Rotating certificate for $NODE ($DAYS_LEFT days left)"

        # Generate new key pair
        openssl genpkey -algorithm Ed25519 -out "$CERT_DIR/${NODE}.key.new"

        # Create CSR
        openssl req -new -key "$CERT_DIR/${NODE}.key.new" \
            -out "$CERT_DIR/${NODE}.csr" \
            -subj "/O=Coffee Pie/CN=${NODE}"

        # Sign with intermediate CA
        openssl x509 -req -days 365 -in "$CERT_DIR/${NODE}.csr" \
            -CA "$CA_DIR/intermediate.crt" \
            -CAkey "$CA_DIR/intermediate.key" \
            -out "$CERT_DIR/${NODE}.crt.new"

        # Atomic swap
        mv "$CERT_DIR/${NODE}.key.new" "$CERT_DIR/${NODE}.key"
        mv "$CERT_DIR/${NODE}.crt.new" "$CERT_DIR/${NODE}.crt"
        rm -f "$CERT_DIR/${NODE}.csr"

        # Reload service
        systemctl reload coffeepie-actor 2>/dev/null || true
        systemctl reload sunshine 2>/dev/null || true

        echo "Rotated $NODE certificate"
    fi
done
```

## Certificate Revocation

### Revoke a compromised node

```bash
# 1. Revoke certificate
openssl ca -revoke /path/to/compromised.crt \
  -keyfile dc1-intermediate.key \
  -cert dc1-intermediate.crt

# 2. Update CRL
openssl ca -gencrl \
  -keyfile dc1-intermediate.key \
  -cert dc1-intermediate.crt \
  -out dc1-intermediate.crl

# 3. Distribute CRL to all nodes
for node in $(cat /etc/coffeepie/nodes.txt); do
    scp dc1-intermediate.crl root@${node}:/etc/coffeepie/ca/
    ssh root@${node} "systemctl reload coffeepie-actor"
done

# 4. Revoke node registration in orchestrator
curl -X DELETE "https://orchestrator/api/v1/nodes/${COMPROMISED_NODE}" \
  -H "Authorization: Bearer ${ORCH_API_KEY}"

# 5. Rotate all keys if root/intermediate CA was compromised
# (Run full re-issuance for all nodes)
```

## Emergency: Full CA Compromise

```bash
# 1. Generate new root CA (offline, air-gapped)
openssl genpkey -algorithm Ed25519 -out root-ca-v2.key
openssl req -new -x509 -days 3650 -key root-ca-v2.key -out root-ca-v2.crt \
  -subj "/O=Coffee Pie/CN=Coffee Pie Internal Root CA v2"

# 2. Generate new intermediate CAs per DC
for dc in dc1 dc2 dc3; do
    openssl genpkey -algorithm Ed25519 -out ${dc}-intermediate-v2.key
    openssl req -new -key ${dc}-intermediate-v2.key -out ${dc}-intermediate-v2.csr \
      -subj "/O=Coffee Pie/CN=${dc^^} Intermediate CA v2"
    openssl x509 -req -days 1825 -in ${dc}-intermediate-v2.csr \
      -CA root-ca-v2.crt -CAkey root-ca-v2.key \
      -out ${dc}-intermediate-v2.crt
done

# 3. Re-issue ALL node certificates (automated)
coffeepie-deploy --phase 4  # Re-run key generation phase
# OR manually for each node...

# 4. Distribute new CA bundle to all codec terminals
# (Done via orchestrator push on next terminal connection)

# 5. Revoke old CA bundle
# Delete old root CA from all trust stores
```

## Compliance Checklist

- [ ] Root CA key stored offline (HSM or air-gapped)
- [ ] Intermediate CA keys on dedicated CA server (not on orchestrator)
- [ ] Node certificates: 365-day validity, auto-rotated at 30 days
- [ ] CRL distributed within 1 hour of revocation
- [ ] All TLS traffic uses mutual TLS (mTLS) on L2/L3/L4 internal network
- [ ] Certificate transparency logs enabled
- [ ] Quarterly audit: check all certs, revoke unused, rotate intermediates

## Integration with coffeepie-keygen

```bash
# Generate all keys for a new datacenter
coffeepie-keygen --purpose dc1-orch --out-dir ./certs/dc1
coffeepie-keygen --purpose dc1-agent --out-dir ./certs/dc1
coffeepie-keygen --purpose dc1-pve-a --out-dir ./certs/dc1
# ... repeat for all nodes
coffeepie-keygen --ca --out-dir ./certs/dc1

# Deploy with coffeepie-deploy
coffeepie-deploy --config dc1-deploy.json --phase 4
```
