


# Stage 1: Builder
FROM ubuntu:24.04 AS builder
 
ENV DEBIAN_FRONTEND=noninteractive \
    QT_VERSION=5 \
    CMAKE_VERSION=3.27
 
RUN apt-get update && apt-get install -y \
    build-essential \
    cmake \
    git \
    wget \
    curl \
    python3 \
    python3-pip \
    libgl1-mesa-dev \
    libxkbcommon-dev \
    libxkbcommon-x11-dev \
    libdbus-1-dev \
    libfontconfig1-dev \
    libfreetype6-dev \
    libx11-dev \
    libxext-dev \
    libxfixes-dev \
    libxi-dev \
    libxrender-dev \
    libxrandr-dev \
    libxcursor-dev \
    libxtst-dev \
    libxinerama-dev \
    qtbase5-dev \
    qtdeclarative5-dev \
    qt5-qmake \
    libqt5core5a \
    libqt5gui5 \
    libqt5qml5 \
    libqt5network5 \
    libqt5dbus5 \
    libqt5widgets5 \
    libqt5sql5 \
    && rm -rf /var/lib/apt/lists/*
 
WORKDIR /build
COPY . .
 
RUN python3 -m pip install --no-cache-dir --break-system-packages -r requirements_current.txt
 
 
# -----------------------------------------------------------------------------
# Stage 2: Runtime
# -----------------------------------------------------------------------------
FROM ubuntu:24.04
 
ENV DEBIAN_FRONTEND=noninteractive \
    DISPLAY=:0 \
    QT_QPA_PLATFORM=xcb \
    QT_AUTO_SCREEN_SCALE_FACTOR=1 \
    QT_XCB_GL_INTEGRATION=none \
    QT_LOGGING_RULES="qt.qpa.*=false;qt.qpa.xcb.*=false" \
    LIBGL_ALWAYS_SOFTWARE=1 \
    PYOPENGL_PLATFORM=osmesa
 
# Runtime deps — xvfb and x11vnc removed (not needed for X11 forwarding)
RUN apt-get update && apt-get install -y \
    wget \
    curl \
    libgl1 \
    libosmesa6 \
    libxkbcommon-x11-0 \
    libdbus-1-3 \
    libfontconfig1 \
    libfreetype6 \
    libx11-6 \
    libxext6 \
    libxfixes3 \
    libxi6 \
    libxrender1 \
    libxrandr2 \
    libxcursor1 \
    libxtst6 \
    libxinerama1 \
    python3 \
    python3-pip \
    ca-certificates \
    libglvnd0 \
    libglx0 \
    libxrender-dev \
    libglib2.0-0 \
    libsm6 \
    libxcb1 \
    libxcb-icccm4 \
    libxcb-image0 \
    libxcb-keysyms1 \
    libxcb-randr0 \
    libxcb-render0 \
    libxcb-render-util0 \
    libxcb-shape0 \
    libxcb-xfixes0 \
    libxcb-xinerama0 \
    libxcb-xkb1 \
    libxkbcommon0 \
    libgssapi-krb5-2 \
    libkrb5-3 \
    libssl3 \
    libnss3 \
    libnspr4 \
    libxss1 \
    libasound2t64 \
    fontconfig-config \
    fonts-dejavu-core \
    libgtk-3-0 \
    libpango-1.0-0 \
    libpangoft2-1.0-0 \
    libdbus-glib-1-2 \
    && rm -rf /var/lib/apt/lists/*    
# Install browser depending on architecture:
#   amd64 → Google Chrome (real .deb from Google)
#   arm64 → Chromium from Debian repos (not a snap)
RUN ARCH=$(dpkg --print-architecture) && \
    echo "Detected architecture: $ARCH" && \
    if [ "$ARCH" = "amd64" ]; then \
        wget -q -O /tmp/google-chrome.deb \
            https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb \
        && apt-get update \
        && apt-get install -y /tmp/google-chrome.deb \
        && rm /tmp/google-chrome.deb \
        && rm -rf /var/lib/apt/lists/* ; \
    elif [ "$ARCH" = "arm64" ]; then \
        apt-get update \
        && apt-get install -y chromium chromium-driver \
        && rm -rf /var/lib/apt/lists/* ; \
    else \
        echo "Unsupported architecture: $ARCH" && exit 1 ; \
    fi






COPY --from=builder /build/CoffeePieContent       /app/CoffeePieContent
COPY --from=builder /build/requirements_current.txt /app/requirements_current.txt
 
RUN python3 -m pip install --no-cache-dir --break-system-packages -r /app/requirements_current.txt && \
    python3 -m pip install --no-cache-dir --break-system-packages -r /app/CoffeePieContent/python/requirements.txt
 
WORKDIR /app
 
# Direct entrypoint — talks to host X server via the mounted socket
ENTRYPOINT ["python3"]
CMD ["CoffeePieContent/python/main.py"]