from __future__ import absolute_import, division, unicode_literals

import os
import pyqrcode

from PIL import Image, ImageDraw, ImageFont, ImageColor

from resources.lib import settings
from resources.lib import tools

_addon_path = tools.translate_path(settings.get_addon_info("path"))
_font = os.path.join(_addon_path, "resources", "fonts", "DankMono-Regular.ttf")

_device_blurb = "With any device, scan the QR code below or visit:"
_url = "https://www.github.com/login/device/"
_code_blurb = "And enter the code:"
_code = "1234-ABCD"

_color = settings.get_setting_string("general.color")
_fg_color = ImageColor.getrgb("#efefefff")
_bg_color = ImageColor.getrgb("#222222ff")


def _center_coords(image_width, image_height, coord_width, coord_height):
    return (
        (image_width // 2) - (coord_width // 2),
        (image_height // 2) - (coord_height // 2),
    )


def generate_qr(content, path, filename):
    if not os.path.exists(path):
        os.makedirs(path)

    qr_file = os.path.join(path, filename)
    qr = pyqrcode.create(content)
    qr.png(
        qr_file, scale=16, module_color=_fg_color, background=_bg_color, quiet_zone=2
    )

    return qr_file


def qr_dialog(qr_image, top_text=None, bottom_text=None):
    with Image.open(qr_image).convert("RGBA") as qr:
        text_layer = Image.new("RGBA", (1920, 1080), _bg_color)

        font = ImageFont.truetype(_font, 40)
        draw_text = ImageDraw.Draw(text_layer)

        qr_coords = _center_coords(1920, 1080, qr.size[0], qr.size[1])
        text_layer.paste(
            qr,
            (
                qr_coords[0],
                qr_coords[1],
                qr_coords[0] + qr.size[0],
                qr_coords[1] + qr.size[1],
            ),
        )

        for idx, line in enumerate(reversed(top_text)):
            line_size = draw_text.textsize(line[0], font)
            line_coords = _center_coords(
                text_layer.size[0], text_layer.size[1], line_size[0], line_size[1]
            )
            draw_text.text(
                (line_coords[0], qr_coords[1] - 8 - (line_size[1] * (idx + 1))),
                line[0],
                font=font,
                fill=ImageColor.getrgb(line[1]),
            )

        for idx, line in enumerate(bottom_text):
            line_size = draw_text.textsize(line[0], font)
            line_coords = _center_coords(
                text_layer.size[0], text_layer.size[1], line_size[0], line_size[1]
            )
            draw_text.text(
                (
                    line_coords[0],
                    qr_coords[1] + qr.size[1] + 8 + (line_size[1] * idx),
                ),
                line[0],
                font=font,
                fill=ImageColor.getrgb(line[1]),
            )

        text_layer.save(qr_image)

        # enter_width, enter_height = draw_text.textsize(_code_blurb, font)
        # enter_coords = _center_coords(1920, 1080, enter_width, enter_height)

        # code_width, code_height = draw_text.textsize(_code, font)
        # code_coords = _center_coords(1920, 1080, code_width, code_height)

        # draw_text.text(
        #     (enter_coords[0], 1080 - 40 - enter_height - code_height),
        #     _code_blurb,
        #     font=font,
        #     fill=_text_color,
        # )
        # draw_text.text(
        #     (code_coords[0], 1080 - 25 - code_height),
        #     _code,
        #     font=font,
        #     fill=_code_color,
        # )
