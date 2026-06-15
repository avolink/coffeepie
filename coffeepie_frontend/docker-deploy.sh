#!/bin/bash
# Docker deployment helper script for CoffeePie

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

print_header() {
    echo -e "${BLUE}===== CoffeePie Docker Deployment =====${NC}"
    echo ""
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

print_info() {
    echo -e "${YELLOW}ℹ $1${NC}"
}

check_docker() {
    if ! command -v docker &> /dev/null; then
        print_error "Docker is not installed. Please install Docker first."
        exit 1
    fi
    print_success "Docker found"
    
    if ! command -v docker-compose &> /dev/null; then
        print_error "Docker Compose is not installed. Please install Docker Compose first."
        exit 1
    fi
    print_success "Docker Compose found"
}

check_x11() {
    if [[ "$OSTYPE" == "linux-gnu"* ]]; then
        if [ -z "$DISPLAY" ]; then
            print_error "DISPLAY variable not set. X11 is not available."
            print_info "Running headless. Set QT_QPA_PLATFORM=offscreen"
            return 1
        fi
        
        if ! xhost +local:docker 2>/dev/null; then
            print_error "Could not add local docker to xhost. Trying without..."
            return 1
        fi
        print_success "X11 display forwarding configured"
        return 0
    fi
}

build_image() {
    print_header
    print_info "Building Docker image..."
    
    cd "$SCRIPT_DIR"
    docker-compose build
    
    if [ $? -eq 0 ]; then
        print_success "Docker image built successfully"
    else
        print_error "Failed to build Docker image"
        exit 1
    fi
}

run_application() {
    print_header
    print_info "Starting CoffeePie application..."
    
    cd "$SCRIPT_DIR"
    
    # Check for X11 availability
    if check_x11; then
        docker-compose up
    else
        print_info "Attempting to run with display forwarding anyway..."
        docker-compose up
    fi
}

run_headless() {
    print_header
    print_info "Starting CoffeePie in headless mode..."
    
    cd "$SCRIPT_DIR"
    docker run -it --rm \
        --env QT_QPA_PLATFORM=offscreen \
        coffeepie:latest
}

stop_application() {
    print_header
    print_info "Stopping CoffeePie..."
    
    cd "$SCRIPT_DIR"
    docker-compose down
    
    print_success "Application stopped"
}

show_logs() {
    print_header
    print_info "Showing application logs..."
    
    cd "$SCRIPT_DIR"
    docker-compose logs -f coffeepie
}

show_menu() {
    print_header
    echo "Select an option:"
    echo "1) Check dependencies"
    echo "2) Build Docker image"
    echo "3) Run application (with X11)"
    echo "4) Run application (headless)"
    echo "5) Stop application"
    echo "6) Show logs"
    echo "7) Exit"
    echo ""
    read -p "Enter your choice [1-7]: " choice
}

# Main menu loop
main() {
    if [ $# -eq 0 ]; then
        while true; do
            show_menu
            case $choice in
                1)
                    check_docker
                    ;;
                2)
                    check_docker
                    build_image
                    ;;
                3)
                    check_docker
                    run_application
                    ;;
                4)
                    check_docker
                    run_headless
                    ;;
                5)
                    stop_application
                    ;;
                6)
                    show_logs
                    ;;
                7)
                    print_info "Exiting"
                    exit 0
                    ;;
                *)
                    print_error "Invalid choice"
                    ;;
            esac
            echo ""
        done
    else
        # Command line arguments support
        case $1 in
            check)
                check_docker
                ;;
            build)
                check_docker
                build_image
                ;;
            run)
                check_docker
                run_application
                ;;
            headless)
                check_docker
                run_headless
                ;;
            stop)
                stop_application
                ;;
            logs)
                show_logs
                ;;
            *)
                print_error "Usage: $0 {check|build|run|headless|stop|logs}"
                exit 1
                ;;
        esac
    fi
}

main "$@"
