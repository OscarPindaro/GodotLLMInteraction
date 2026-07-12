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
#   install-godot.sh <binary> <name> [icon_path]   Manual install (legacy mode)
# ---------------------------------------------------------------------------

# --- Constants -------------------------------------------------------------

OPT_DIR="/opt/godot"
BIN_DIR="$HOME/.local/bin"
APPS_DIR="$HOME/.local/share/applications"
ICONS_DIR="$HOME/.local/share/icons"
GITHUB_LATEST="https://api.github.com/repos/godotengine/godot/releases/latest"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# --- Functions -------------------------------------------------------------

usage() {
    cat <<EOF
Usage: $(basename "$0") <command> [options]

Commands:
  list                    List installed Godot versions (oldest to newest)
  install [-y]            Download and install the latest Godot stable release
  switch [version]        Switch the active Godot version (interactive if no arg)
  <binary> <name> [icon]  Manually install a Godot binary (legacy mode)

Options:
  -y, --yes               Skip confirmation prompt (install command)

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
        echo "Error: '$name' is not installed."
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
        echo "⚠ Warning: '$resolved' shadows $BIN_DIR/godot in PATH."
        echo "  Remove it with: sudo rm $resolved"
    fi
}

ensure_opt_dir() {
    if [[ ! -d "$OPT_DIR" ]]; then
        echo "Creating $OPT_DIR (requires sudo)..."
        sudo mkdir -p "$OPT_DIR"
        sudo chown "$USER" "$OPT_DIR"
        echo "Done. Future installs won't need sudo."
    elif [[ ! -w "$OPT_DIR" ]]; then
        echo "$OPT_DIR exists but is not writable. Fixing ownership (requires sudo)..."
        sudo chown "$USER" "$OPT_DIR"
    fi
}

install_binary() {
    local binary="$1" name="$2" icon_path="${3:-}"

    # Validate
    if [[ ! -f "$binary" ]]; then
        echo "Error: executable '$binary' not found."
        exit 1
    fi
    if [[ ! -x "$binary" ]]; then
        echo "Error: '$binary' is not executable. Run: chmod +x $binary"
        exit 1
    fi
    if [[ -n "$icon_path" ]]; then
        if [[ ! -f "$icon_path" ]]; then
            echo "Error: icon file '$icon_path' not found."
            exit 1
        fi
        local ext="${icon_path##*.}"
        ext="${ext,,}"
        if [[ "$ext" != "png" && "$ext" != "svg" ]]; then
            echo "Error: icon must be a .png or .svg file (got .$ext)."
            exit 1
        fi
    fi

    # Ensure directories
    ensure_opt_dir
    mkdir -p "$BIN_DIR" "$APPS_DIR" "$ICONS_DIR"

    # Copy binary
    local dest_binary="$OPT_DIR/$name"
    echo "Copying binary to $dest_binary..."
    cp "$binary" "$dest_binary"
    chmod +x "$dest_binary"

    # Symlink
    local symlink="$BIN_DIR/$name"
    if [[ -L "$symlink" || -e "$symlink" ]]; then
        echo "Removing existing symlink/file at $symlink..."
        rm "$symlink"
    fi
    echo "Creating symlink $symlink -> $dest_binary..."
    ln -s "$dest_binary" "$symlink"

    # Icon (copy as-is, no conversion needed — desktop envs support SVG)
    local desktop_icon=""
    if [[ -n "$icon_path" ]]; then
        local ext="${icon_path##*.}"
        ext="${ext,,}"
        local dest_icon="$ICONS_DIR/$name.$ext"
        cp "$icon_path" "$dest_icon"
        echo "Icon installed at $dest_icon."
        desktop_icon="$dest_icon"
    fi

    # .desktop file
    local desktop_file="$APPS_DIR/$name.desktop"
    echo "Creating desktop entry at $desktop_file..."
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
    echo "✅ Godot '$name' installed successfully!"
    echo "   Binary:  $dest_binary"
    echo "   Symlink: $symlink"
    echo "   Active:  $BIN_DIR/godot -> $dest_binary"
    echo "   Launcher: $desktop_file"
    [[ -n "$desktop_icon" ]] && echo "   Icon:    $desktop_icon"
    echo ""
    echo "You can now run it with: godot (or $name for this specific version)"
}

cmd_list() {
    if [[ ! -d "$OPT_DIR" ]]; then
        echo "No Godot installations found."
        return
    fi

    local entries=()
    while IFS= read -r f; do
        entries+=("$(basename "$f")")
    done < <(find "$OPT_DIR" -maxdepth 1 -type f -executable | sort -V)

    if [[ ${#entries[@]} -eq 0 ]]; then
        echo "No Godot installations found."
        return
    fi

    echo "Installed Godot versions (oldest → newest):"
    local active
    active="$(get_active_version 2>/dev/null || true)"
    for e in "${entries[@]}"; do
        if [[ "$e" == "$active" ]]; then
            echo "  * $e  (active)"
        else
            echo "    $e"
        fi
    done

    # Check for updates
    local latest
    latest="$(get_latest_tag 2>/dev/null || true)"
    if [[ -n "$latest" ]]; then
        echo ""
        if [[ -f "$OPT_DIR/godot-$latest" ]]; then
            echo "Latest available: $latest ✓ (up to date)"
        else
            echo "Latest available: $latest (update available — run '$(basename "$0") install')"
        fi
    fi
}

cmd_install() {
    local auto_yes=false
    while [[ $# -gt 0 ]]; do
        case "$1" in
            -y|--yes) auto_yes=true; shift ;;
            *) echo "Unknown option: $1"; exit 1 ;;
        esac
    done

    # Check dependencies
    local pkg_mgr
    pkg_mgr="$(detect_pkg_manager)"
    for cmd in curl unzip; do
        if ! command -v "$cmd" &>/dev/null; then
            if [[ -n "$pkg_mgr" ]]; then
                echo "Error: $cmd is required. Install with: sudo $pkg_mgr install $cmd"
            else
                echo "Error: $cmd is required but was not found."
            fi
            exit 1
        fi
    done

    echo "Checking latest Godot release..."
    local tag
    tag="$(get_latest_tag)"
    if [[ -z "$tag" ]]; then
        echo "Error: could not determine latest Godot release."
        exit 1
    fi
    echo "Latest release: $tag"

    local name="godot-$tag"
    local dest_binary="$OPT_DIR/$name"

    if [[ -f "$dest_binary" ]]; then
        echo "Godot $tag is already installed."
        exit 0
    fi

    if [[ "$auto_yes" != true ]]; then
        read -rp "Install Godot $tag? [y/N] " confirm
        if [[ "$confirm" != [yY] ]]; then
            echo "Aborted."
            exit 0
        fi
    fi

    # Download
    local url="https://github.com/godotengine/godot/releases/download/${tag}/Godot_v${tag}_linux.x86_64.zip"
    local tmpdir
    tmpdir="$(mktemp -d)"
    trap 'rm -rf "$tmpdir"' EXIT

    echo "Downloading $url..."
    if ! curl -fL -o "$tmpdir/godot.zip" "$url"; then
        echo "Error: download failed."
        exit 1
    fi

    echo "Extracting..."
    unzip -o "$tmpdir/godot.zip" -d "$tmpdir" >/dev/null

    # Find the binary
    local extracted
    extracted="$(find "$tmpdir" -type f -name "Godot*" | head -1)"
    if [[ -z "$extracted" ]]; then
        echo "Error: could not find Godot binary in archive."
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
        echo "No Godot installations found."
        exit 1
    fi

    local entries=()
    while IFS= read -r f; do
        entries+=("$(basename "$f")")
    done < <(find "$OPT_DIR" -maxdepth 1 -type f -executable | sort -V)

    if [[ ${#entries[@]} -eq 0 ]]; then
        echo "No Godot installations found."
        exit 1
    fi

    if [[ -z "$target" ]]; then
        # Interactive selection
        local active
        active="$(get_active_version 2>/dev/null || true)"
        echo "Installed Godot versions:"
        for i in "${!entries[@]}"; do
            local marker=" "
            if [[ "${entries[$i]}" == "$active" ]]; then
                marker="*"
            fi
            echo "  [$((i+1))] $marker ${entries[$i]}"
        done
        echo ""
        read -rp "Select version (1-${#entries[@]}): " choice
        if [[ "$choice" =~ ^[0-9]+$ ]] && (( choice >= 1 && choice <= ${#entries[@]} )); then
            target="${entries[$((choice-1))]}"
        else
            echo "Invalid selection."
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
            echo "Error: no installed version matches '$target'."
            echo "Installed versions:"
            for e in "${entries[@]}"; do echo "  $e"; done
            exit 1
        elif [[ ${#matches[@]} -gt 1 ]]; then
            echo "Error: multiple matches for '$target':"
            for m in "${matches[@]}"; do echo "  $m"; done
            exit 1
        fi
        target="${matches[0]}"
    fi

    set_active_version "$target"
    echo "Switched active Godot to: $target"
    echo "  $BIN_DIR/godot -> $OPT_DIR/$target"
}

# --- Main ------------------------------------------------------------------

main() {
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
