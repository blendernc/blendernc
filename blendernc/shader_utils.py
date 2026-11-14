basic_shader_nodes = {
    "Attribute": {
        "type": "ShaderNodeAttribute",
        "links": {
            "Color": {
                "ShaderNodeMapRange": "Value",
            }
        },
    },
    "Attribute.001": {
        "type": "ShaderNodeAttribute",
        "links": {
            "Color": {
                "ShaderNodeMapRange": "From Max",
            }
        },
    },
    "Attribute.002": {
        "type": "ShaderNodeAttribute",
        "links": {
            "Color": {
                "ShaderNodeMapRange": "From Min",
            }
        },
    },
    "ShaderNodeMapRange": {
        "links": {
            "Result": {
                "ShaderNodeValToRGB": "Factor",
            }
        }
    },
    "ShaderNodeValToRGB": {
        "links": {
            "Color": {
                "ShaderNodeBsdfPrincipled": "Base Color",
            }
        }
    },
    "ShaderNodeBsdfPrincipled": {},
    "ShaderNodeOutputMaterial": {},
}

shader_locations = [
    (-500, 200),
    (-500, -200),
    (-500, 0),
    (-300, 0),
    (-100, 0),
    (200, 0),
    (500, 0),
]
