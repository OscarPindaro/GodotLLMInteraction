#!/usr/bin/env bash
set -euo pipefail

# ---------------------------------------------------------------------------
# install-godot.sh
# A CLI for managing Godot engine installations on Linux.
#
# Usage:
#   install-godot.sh list                          List installed Godot versions
#   install-godot.sh install [-y]                 Download & install latest stable
#   install-godot.sh switch [version]             Switch active Godot version
#   install-godot.sh register <binary> <name> [icon]  Register a compiled Godot binary
#   install-godot.sh sanitize [--remove]            Check for orphaned entries; remove if --remove
#   install-godot.sh <binary> <name> [icon_path]   Manual install (legacy mode)
# ---------------------------------------------------------------------------

# --- Constants -------------------------------------------------------------

OPT_DIR="/opt/godot"
BIN_DIR="$HOME/.local/bin"
APPS_DIR="$HOME/.local/share/applications"
ICONS_DIR="$HOME/.local/share/icons"
GITHUB_LATEST="https://api.github.com/repos/godotengine/godot/releases/latest"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

USE_COLOR=true

# --- Color helpers ---------------------------------------------------------

if [[ -t 1 ]]; then
    C_RED="\033[31m"
    C_GREEN="\033[32m"
    C_YELLOW="\033[33m"
    C_CYAN="\033[36m"
    C_WHITE="\033[37m"
    C_BOLD="\033[1m"
    C_RESET="\033[0m"
else
    C_RED="" C_GREEN="" C_YELLOW="" C_CYAN="" C_WHITE="" C_BOLD="" C_RESET=""
fi

print_success() {
    local msg="$1" bold="${2:-false}"
    if [[ "$USE_COLOR" != true ]]; then
        echo -e "$msg"
        return
    fi
    if [[ "$bold" == true ]]; then
        echo -e "${C_BOLD}${C_GREEN}${msg}${C_RESET}"
    else
        echo -e "${C_GREEN}${msg}${C_RESET}"
    fi
}

print_error() {
    local msg="$1" bold="${2:-true}"
    if [[ "$USE_COLOR" != true ]]; then
        echo -e "$msg" >&2
        return
    fi
    if [[ "$bold" == true ]]; then
        echo -e "${C_BOLD}${C_RED}${msg}${C_RESET}" >&2
    else
        echo -e "${C_RED}${msg}${C_RESET}" >&2
    fi
}

print_warning() {
    local msg="$1" bold="${2:-false}"
    if [[ "$USE_COLOR" != true ]]; then
        echo -e "$msg"
        return
    fi
    if [[ "$bold" == true ]]; then
        echo -e "${C_BOLD}${C_YELLOW}${msg}${C_RESET}"
    else
        echo -e "${C_YELLOW}${msg}${C_RESET}"
    fi
}

print_info() {
    local msg="$1" bold="${2:-false}"
    if [[ "$USE_COLOR" != true ]]; then
        echo -e "$msg"
        return
    fi
    if [[ "$bold" == true ]]; then
        echo -e "${C_BOLD}${C_CYAN}${msg}${C_RESET}"
    else
        echo -e "${C_CYAN}${msg}${C_RESET}"
    fi
}

print_detail() {
    local msg="$1" bold="${2:-false}"
    if [[ "$USE_COLOR" != true ]]; then
        echo -e "$msg"
        return
    fi
    if [[ "$bold" == true ]]; then
        echo -e "${C_BOLD}${C_WHITE}${msg}${C_RESET}"
    else
        echo -e "${C_WHITE}${msg}${C_RESET}"
    fi
}

# --- Functions -------------------------------------------------------------

usage() {
    cat <<EOF
Usage: $(basename "$0") <command> [options]

Commands:
  list                    List installed Godot versions (oldest to newest)
  install [-y]            Download and install the latest Godot stable release
  switch [version]        Switch the active Godot version (interactive if no arg)
  register <binary> <name> [icon]  Register a compiled Godot binary
  sanitize [--remove] [--repair]  Check for orphaned entries
  <binary> <name> [icon]  Manually install a Godot binary (legacy mode)

Options:
  --no-color              Disable colored output
  -y, --yes               Skip confirmation prompt (install command)
  --remove                Remove orphaned entries (sanitize command)
  --repair                Create missing .desktop entries for installed binaries (sanitize)

The `godot` command and `godot.desktop` launcher always point to the active
version. Use `switch` to change it. Each version also gets its own
`godot-<version>.desktop` entry for direct launching from the app menu.
EOF
}

get_latest_tag() {
    curl -s "$GITHUB_LATEST" | grep '"tag_name"' | head -1 | cut -d'"' -f4
}

detect_pkg_manager() {
    if command -v dnf &>/dev/null; then
        echo "dnf"
    elif command -v apt &>/dev/null; then
        echo "apt"
    elif command -v pacman &>/dev/null; then
        echo "pacman"
    elif command -v zypper &>/dev/null; then
        echo "zypper"
    else
        echo ""
    fi
}

get_active_version() {
    local symlink="$BIN_DIR/godot"
    if [[ -L "$symlink" ]]; then
        basename "$(readlink -f "$symlink")"
    fi
}

set_active_version() {
    local name="$1"
    local dest_binary="$OPT_DIR/$name"

    if [[ ! -f "$dest_binary" ]]; then
        print_error "Error: '$name' is not installed."
        exit 1
    fi

    # Update godot symlink
    local symlink="$BIN_DIR/godot"
    if [[ -L "$symlink" || -e "$symlink" ]]; then
        rm "$symlink"
    fi
    ln -s "$dest_binary" "$symlink"

    # Update generic godot.desktop
    local desktop_file="$APPS_DIR/godot.desktop"
    local icon=""
    if [[ -f "$ICONS_DIR/$name.svg" ]]; then
        icon="$ICONS_DIR/$name.svg"
    elif [[ -f "$ICONS_DIR/$name.png" ]]; then
        icon="$ICONS_DIR/$name.png"
    fi
    cat > "$desktop_file" <<EOF
[Desktop Entry]
Type=Application
Name=Godot
Exec=$dest_binary
Icon=${icon}
Categories=Development;IDE;
StartupNotify=false
EOF
    chmod +x "$desktop_file"

    if command -v update-desktop-database &>/dev/null; then
        update-desktop-database "$APPS_DIR"
    fi

    # Warn about conflicting godot binaries in PATH
    local resolved
    resolved="$(command -v godot 2>/dev/null || true)"
    if [[ -n "$resolved" && "$resolved" != "$BIN_DIR/godot" ]]; then
        print_warning "Warning: '$resolved' shadows $BIN_DIR/godot in PATH."
        print_warning "  Remove it with: sudo rm $resolved"
    fi
}

ensure_opt_dir() {
    if [[ ! -d "$OPT_DIR" ]]; then
        print_info "Creating $OPT_DIR (requires sudo)..."
        sudo mkdir -p "$OPT_DIR"
        sudo chown "$USER" "$OPT_DIR"
        print_success "Done. Future installs won't need sudo."
    elif [[ ! -w "$OPT_DIR" ]]; then
        print_warning "$OPT_DIR exists but is not writable. Fixing ownership (requires sudo)..."
        sudo chown "$USER" "$OPT_DIR"
    fi
}

install_binary() {
    local binary="$1" name="$2" icon_path="${3:-}"

    # Validate
    if [[ ! -f "$binary" ]]; then
        print_error "Error: executable '$binary' not found."
        exit 1
    fi
    if [[ ! -x "$binary" ]]; then
        print_error "Error: '$binary' is not executable. Run: chmod +x $binary"
        exit 1
    fi
    if [[ -n "$icon_path" ]]; then
        if [[ ! -f "$icon_path" ]]; then
            print_error "Error: icon file '$icon_path' not found."
            exit 1
        fi
        local ext="${icon_path##*.}"
        ext="${ext,,}"
        if [[ "$ext" != "png" && "$ext" != "svg" ]]; then
            print_error "Error: icon must be a .png or .svg file (got .$ext)."
            exit 1
        fi
    fi

    # Ensure directories
    ensure_opt_dir
    mkdir -p "$BIN_DIR" "$APPS_DIR" "$ICONS_DIR"

    # Copy binary
    local dest_binary="$OPT_DIR/$name"
    print_info "Copying binary to $dest_binary..."
    cp "$binary" "$dest_binary"
    chmod +x "$dest_binary"

    # Symlink
    local symlink="$BIN_DIR/$name"
    if [[ -L "$symlink" || -e "$symlink" ]]; then
        print_info "Removing existing symlink/file at $symlink..."
        rm "$symlink"
    fi
    print_info "Creating symlink $symlink -> $dest_binary..."
    ln -s "$dest_binary" "$symlink"

    # Icon (copy as-is, no conversion needed -- desktop envs support SVG)
    local desktop_icon=""
    if [[ -n "$icon_path" ]]; then
        local ext="${icon_path##*.}"
        ext="${ext,,}"
        local dest_icon="$ICONS_DIR/$name.$ext"
        cp "$icon_path" "$dest_icon"
        print_info "Icon installed at $dest_icon."
        desktop_icon="$dest_icon"
    fi

    # .desktop file
    local desktop_file="$APPS_DIR/$name.desktop"
    print_info "Creating desktop entry at $desktop_file..."
    cat > "$desktop_file" <<EOF
[Desktop Entry]
Type=Application
Name=$name
Exec=$dest_binary
Icon=${desktop_icon}
Categories=Development;IDE;
StartupNotify=false
EOF
    chmod +x "$desktop_file"

    # Refresh desktop database
    if command -v update-desktop-database &>/dev/null; then
        update-desktop-database "$APPS_DIR"
    fi

    # Set as active version (updates `godot` symlink + generic desktop entry)
    set_active_version "$name"

    # Success message
    echo ""
    print_success "Godot '$name' installed successfully!" true
    print_detail "   Binary:  $dest_binary"
    print_detail "   Symlink: $symlink"
    print_detail "   Active:  $BIN_DIR/godot -> $dest_binary"
    print_detail "   Launcher: $desktop_file"
    [[ -n "$desktop_icon" ]] && print_detail "   Icon:    $desktop_icon"
    echo ""
    print_info "You can now run it with: godot (or $name for this specific version)"
}

cmd_register() {
    local binary="${1:-}" name="${2:-}" icon="${3:-}"

    if [[ -z "$binary" || -z "$name" ]]; then
        print_error "Usage: $(basename "$0") register <binary> <name> [icon]"
        exit 1
    fi

    install_binary "$binary" "$name" "$icon"
}

cmd_list() {
    if [[ ! -d "$OPT_DIR" ]]; then
        print_warning "No Godot installations found."
        return
    fi

    local entries=()
    while IFS= read -r f; do
        entries+=("$(basename "$f")")
    done < <(find "$OPT_DIR" -maxdepth 1 -type f -executable | sort -V)

    if [[ ${#entries[@]} -eq 0 ]]; then
        print_warning "No Godot installations found."
        return
    fi

    print_info "Installed Godot versions (oldest to newest):" true
    local active
    active="$(get_active_version 2>/dev/null || true)"
    for e in "${entries[@]}"; do
        if [[ "$e" == "$active" ]]; then
            print_success "  * $e  (active)"
        else
            print_detail "    $e"
        fi
    done

    # Check for updates
    local latest
    latest="$(get_latest_tag 2>/dev/null || true)"
    if [[ -n "$latest" ]]; then
        echo ""
        if [[ -f "$OPT_DIR/godot-$latest" ]]; then
            print_success "Latest available: $latest (up to date)"
        else
            print_warning "Latest available: $latest (update available -- run '$(basename "$0") install')"
        fi
    fi
}

cmd_install() {
    local auto_yes=false
    while [[ $# -gt 0 ]]; do
        case "$1" in
            -y|--yes) auto_yes=true; shift ;;
            *) print_error "Unknown option: $1"; exit 1 ;;
        esac
    done

    # Check dependencies
    local pkg_mgr
    pkg_mgr="$(detect_pkg_manager)"
    for cmd in curl unzip; do
        if ! command -v "$cmd" &>/dev/null; then
            if [[ -n "$pkg_mgr" ]]; then
                print_error "Error: $cmd is required. Install with: sudo $pkg_mgr install $cmd"
            else
                print_error "Error: $cmd is required but was not found."
            fi
            exit 1
        fi
    done

    print_info "Checking latest Godot release..."
    local tag
    tag="$(get_latest_tag)"
    if [[ -z "$tag" ]]; then
        print_error "Error: could not determine latest Godot release."
        exit 1
    fi
    print_info "Latest release: $tag"

    local name="godot-$tag"
    local dest_binary="$OPT_DIR/$name"

    if [[ -f "$dest_binary" ]]; then
        print_success "Godot $tag is already installed."
        exit 0
    fi

    if [[ "$auto_yes" != true ]]; then
        read -rp "Install Godot $tag? [y/N] " confirm
        if [[ "$confirm" != [yY] ]]; then
            print_warning "Aborted."
            exit 0
        fi
    fi

    # Download
    local url="https://github.com/godotengine/godot/releases/download/${tag}/Godot_v${tag}_linux.x86_64.zip"
    local tmpdir
    tmpdir="$(mktemp -d)"
    trap 'rm -rf "$tmpdir"' EXIT

    print_info "Downloading $url..."
    if ! curl -fL -o "$tmpdir/godot.zip" "$url"; then
        print_error "Error: download failed."
        exit 1
    fi

    print_info "Extracting..."
    unzip -o "$tmpdir/godot.zip" -d "$tmpdir" >/dev/null

    # Find the binary
    local extracted
    extracted="$(find "$tmpdir" -type f -name "Godot*" | head -1)"
    if [[ -z "$extracted" ]]; then
        print_error "Error: could not find Godot binary in archive."
        exit 1
    fi
    chmod +x "$extracted"

    # Icon (use repo's icon.svg if available)
    local icon=""
    if [[ -f "$SCRIPT_DIR/icon.svg" ]]; then
        icon="$SCRIPT_DIR/icon.svg"
    fi

    install_binary "$extracted" "$name" "$icon"

    # Cleanup
    rm -rf "$tmpdir"
    trap - EXIT
}

cmd_switch() {
    local target="${1:-}"

    if [[ ! -d "$OPT_DIR" ]]; then
        print_warning "No Godot installations found."
        exit 1
    fi

    local entries=()
    while IFS= read -r f; do
        entries+=("$(basename "$f")")
    done < <(find "$OPT_DIR" -maxdepth 1 -type f -executable | sort -V)

    if [[ ${#entries[@]} -eq 0 ]]; then
        print_warning "No Godot installations found."
        exit 1
    fi

    if [[ -z "$target" ]]; then
        # Interactive selection
        local active
        active="$(get_active_version 2>/dev/null || true)"
        print_info "Installed Godot versions:" true
        for i in "${!entries[@]}"; do
            local marker=" "
            if [[ "${entries[$i]}" == "$active" ]]; then
                marker="*"
            fi
            print_detail "  [$((i+1))] $marker ${entries[$i]}"
        done
        echo ""
        read -rp "Select version (1-${#entries[@]}): " choice
        if [[ "$choice" =~ ^[0-9]+$ ]] && (( choice >= 1 && choice <= ${#entries[@]} )); then
            target="${entries[$((choice-1))]}"
        else
            print_error "Invalid selection."
            exit 1
        fi
    else
        # Match by name (allow partial match on version part)
        local matches=()
        for e in "${entries[@]}"; do
            if [[ "$e" == "$target" || "$e" == "godot-$target" ]]; then
                matches+=("$e")
            fi
        done
        if [[ ${#matches[@]} -eq 0 ]]; then
            print_error "Error: no installed version matches '$target'."
            print_info "Installed versions:"
            for e in "${entries[@]}"; do print_detail "  $e"; done
            exit 1
        elif [[ ${#matches[@]} -gt 1 ]]; then
            print_error "Error: multiple matches for '$target':"
            for m in "${matches[@]}"; do print_detail "  $m"; done
            exit 1
        fi
        target="${matches[0]}"
    fi

    set_active_version "$target"
    print_success "Switched active Godot to: $target" true
    print_detail "  $BIN_DIR/godot -> $OPT_DIR/$target"
}

cmd_sanitize() {
    local do_remove=false do_repair=false
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --remove) do_remove=true; shift ;;
            --repair) do_repair=true; shift ;;
            *) print_error "Unknown option: $1"; exit 1 ;;
        esac
    done

    local issues=0
    increment_issues() { ((issues++)) || true; }

    # 1. Check .desktop files that reference missing binaries
    local orphaned_desktops=()
    if [[ -d "$APPS_DIR" ]]; then
        for df in "$APPS_DIR"/godot*.desktop; do
            [[ -f "$df" ]] || continue
            local exec_line
            exec_line="$(grep -m1 '^Exec=' "$df" | cut -d= -f2-)"
            local bin_path
            bin_path="$(echo "$exec_line" | awk '{print $1}')"
            if [[ -n "$bin_path" && ! -f "$bin_path" ]]; then
                orphaned_desktops+=("$(basename "$df")")
            fi
        done
    fi

    # 2. Check symlinks in BIN_DIR that point to missing binaries
    local orphaned_symlinks=()
    if [[ -d "$BIN_DIR" ]]; then
        for sl in "$BIN_DIR"/godot*; do
            [[ -L "$sl" ]] || continue
            local target
            target="$(readlink -f "$sl")"
            if [[ ! -f "$target" ]]; then
                orphaned_symlinks+=("$(basename "$sl")")
            fi
        done
    fi

    # 3. Check icons that have no corresponding binary
    local orphaned_icons=()
    if [[ -d "$ICONS_DIR" ]]; then
        for ic in "$ICONS_DIR"/godot*; do
            [[ -f "$ic" ]] || continue
            local base
            base="$(basename "$ic")"
            base="${base%.*}"  # strip extension
            if [[ ! -f "$OPT_DIR/$base" ]]; then
                orphaned_icons+=("$(basename "$ic")")
            fi
        done
    fi

    # 4. Check binaries in OPT_DIR that have no corresponding .desktop
    local orphaned_binaries=()
    if [[ -d "$OPT_DIR" ]]; then
        while IFS= read -r f; do
            local base
            base="$(basename "$f")"
            if [[ ! -f "$APPS_DIR/$base.desktop" ]]; then
                orphaned_binaries+=("$base")
            fi
        done < <(find "$OPT_DIR" -maxdepth 1 -type f -executable 2>/dev/null || true)
    fi

    # Report
    if [[ ${#orphaned_desktops[@]} -gt 0 ]]; then
        print_warning "Orphaned .desktop files (binary missing):"
        for d in "${orphaned_desktops[@]}"; do print_detail "  $APPS_DIR/$d"; done
        increment_issues
    fi
    if [[ ${#orphaned_symlinks[@]} -gt 0 ]]; then
        print_warning "Orphaned symlinks (target missing):"
        for s in "${orphaned_symlinks[@]}"; do print_detail "  $BIN_DIR/$s"; done
        increment_issues
    fi
    if [[ ${#orphaned_icons[@]} -gt 0 ]]; then
        print_warning "Orphaned icons (no corresponding binary):"
        for i in "${orphaned_icons[@]}"; do print_detail "  $ICONS_DIR/$i"; done
        increment_issues
    fi
    if [[ ${#orphaned_binaries[@]} -gt 0 ]]; then
        print_info "Binaries without .desktop entry (use --repair to fix):"
        for b in "${orphaned_binaries[@]}"; do print_detail "  $OPT_DIR/$b"; done
        increment_issues
    fi

    if [[ $issues -eq 0 ]]; then
        print_success "No issues found. All entries are consistent." true
        return
    fi

    # --repair: create missing .desktop entries and symlinks for installed binaries
    if [[ "$do_repair" == true ]]; then
        for b in "${orphaned_binaries[@]}"; do
            local icon=""
            if [[ -f "$ICONS_DIR/$b.svg" ]]; then
                icon="$ICONS_DIR/$b.svg"
            elif [[ -f "$ICONS_DIR/$b.png" ]]; then
                icon="$ICONS_DIR/$b.png"
            elif [[ -f "$SCRIPT_DIR/icon.svg" ]]; then
                icon="$SCRIPT_DIR/icon.svg"
            fi
            print_info "Repairing: creating .desktop + symlink for $b ..."
            # Create symlink if missing
            local sl="$BIN_DIR/$b"
            if [[ ! -L "$sl" ]]; then
                ln -s "$OPT_DIR/$b" "$sl"
                print_detail "  Created symlink: $sl -> $OPT_DIR/$b"
            fi
            # Create .desktop if missing
            local df="$APPS_DIR/$b.desktop"
            if [[ ! -f "$df" ]]; then
                cat > "$df" <<EOF2
[Desktop Entry]
Type=Application
Name=$b
Exec=$OPT_DIR/$b
Icon=${icon}
Categories=Development;IDE;
StartupNotify=false
EOF2
                chmod +x "$df"
                print_detail "  Created desktop entry: $df"
            fi
        done
        if command -v update-desktop-database &>/dev/null; then
            update-desktop-database "$APPS_DIR"
        fi
        print_success "Repair complete." true
    fi

    if [[ "$do_remove" != true && "$do_repair" != true ]]; then
        echo ""
        print_info "Run with --remove to clean up orphaned entries, or --repair to create missing ones."
        return
    fi

    # Confirm before removal
    local active
    active="$(get_active_version 2>/dev/null || true)"

    echo ""
    read -rp "Remove all orphaned entries? [y/N] " confirm
    if [[ "$confirm" != [yY] ]]; then
        print_warning "Aborted."
        return
    fi

    for d in "${orphaned_desktops[@]}"; do
        rm -f "$APPS_DIR/$d"
        print_detail "Removed: $APPS_DIR/$d"
    done
    for s in "${orphaned_symlinks[@]}"; do
        rm -f "$BIN_DIR/$s"
        print_detail "Removed: $BIN_DIR/$s"
    done
    for i in "${orphaned_icons[@]}"; do
        rm -f "$ICONS_DIR/$i"
        print_detail "Removed: $ICONS_DIR/$i"
    done
    # Note: binaries without .desktop entries are NOT removed by --remove.
    # Use --repair to create their missing .desktop entries instead.

    if command -v update-desktop-database &>/dev/null; then
        update-desktop-database "$APPS_DIR"
    fi

    print_success "Cleanup complete." true
}

# --- Main ------------------------------------------------------------------

main() {
    # Parse global flags before command
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --no-color)
                USE_COLOR=false
                shift
                ;;
            *)
                break
                ;;
        esac
    done

    local cmd="${1:-}"

    case "$cmd" in
        list)
            cmd_list
            ;;
        install)
            shift
            cmd_install "$@"
            ;;
        switch)
            shift
            cmd_switch "$@"
            ;;
        register)
            shift
            cmd_register "$@"
            ;;
        sanitize)
            shift
            cmd_sanitize "$@"
            ;;
        -h|--help|help)
            usage
            ;;
        "")
            usage
            exit 1
            ;;
        *)
            # Legacy mode: manual install <binary> <name> [icon]
            local binary="$cmd" name="${2:-}" icon="${3:-}"
            if [[ -z "$name" ]]; then
                usage
                exit 1
            fi
            install_binary "$binary" "$name" "$icon"
            ;;
    esac
}

main "$@"
