#!/usr/bin/env fish

function copy_empty_structure
    set src $argv[1]
    set dest $argv[2]

    if test -z "$src" -o -z "$dest"
        echo "Usage: copy_structure_with_assets.fish <source_dir> <destination_dir>"
        return 1
    end

    if not test -d "$src"
        echo "❌ Source directory does not exist: $src"
        return 1
    end

    # Define which file extensions are considered "assets" to be copied with content
    set asset_exts png jpg jpeg gif webp svg ico mp4 mp3 wav ogg ttf otf woff woff2 zip gz tar

    # Make the destination directory
    mkdir -p "$dest"

    # Step 1: Copy all directories except .git
    for dir in (find $src -type d -not -path "*/.git/*")
        set rel_dir (string replace -r "^$src/?(.*)" '$1' $dir)
        mkdir -p "$dest/$rel_dir"
    end

    # Step 2: Handle files
    for file in (find $src -type f -not -path "*/.git/*")
        set rel_file (string replace -r "^$src/?(.*)" '$1' $file)
        set target_file "$dest/$rel_file"

        # Get extension without dot, lowercase
        set ext (string lower (string split -r "." -- $file)[-1])

        # If the file is an asset, copy it
        if contains $ext $asset_exts
            if not test -e "$target_file"
                cp "$file" "$target_file"
            end
        else
            # Otherwise, just create an empty file if it doesn't exist
            if not test -e "$target_file"
                touch "$target_file"
            end
        end
    end

    echo "✅ Structure copied. Assets preserved, other files empty, .git skipped."
end
