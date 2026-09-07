#!/bin/bash

# Define the function to run Blender tests
run_blender_tests() {
    # Define an array of Blender versions
    ver_blender=('5.2.0')

    # Loop through each version and run the docker command
    for version in "${ver_blender[@]}"; do
        read -rep "Run tests in Blender "$version", do you want to continue? " -n 1
        docker run -w /blendernc --rm --mount type=bind,source="$(pwd)",target=/blendernc \
        -t ghcr.io/ranchcomputing/blender-cpu-image:"$version" /bin/sh -c "bash /blendernc/tests/build-test.sh"
    done
}

# Call the function
run_blender_tests

