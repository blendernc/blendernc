#!/bin/bash

# Define the function to run Blender tests
run_blender_tests() {
    # Define an array of Blender versions
    ver_blender=('4.2.0' '4.1.0' '3.6.3' '3.3.12' '2.93')

    # Loop through each version and run the docker command
    for version in "${ver_blender[@]}"; do
        read -rep "Version "$version" ran, do you want to continue?" -n 1
        echo "Running tests for Blender version: $version"
        docker run -w /blendernc --rm --mount type=bind,source="$(pwd)",target=/blendernc \
        -t ghcr.io/ranchcomputing/blender-cpu-image:"$version" /bin/sh -c "bash ./tests/build-test.sh"
    done
}

# Call the function
run_blender_tests

