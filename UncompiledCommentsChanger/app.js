const fs = require("fs");
const path = require("path");

function launch() {
    if (fs.existsSync("input") && fs.existsSync("output")) {
        let inputDir = fs.readdirSync("input", {
            recursive: true,
        });
        inputDir.forEach((filepath) => {
            if (path.extname(filepath) === ".rpy") {
                readRewriteFile(`${filepath}`);
            } else if (
                fs.lstatSync(`input\\${filepath}`).isDirectory() === true &&
                fs.existsSync(`output\\${filepath}`) !== true
            ) {
                fs.mkdirSync(`output\\${filepath}`);
            }
        });
    } else {
        throw new Error("Dirs does not exists.");
    }
}

function readRewriteFile(filepath) {
    if (fs.existsSync(`input\\${filepath}`)) {
        let data = fs.readFileSync(`input\\${filepath}`).toString().split("\n");

        data = data.slice(0, -1);
        data[data.length - 1] =
            "\n  # Decompiled by unrpyc_v1.2.0-alpha: https://github.com/CensoredUsername/unrpyc";

        let file = fs.createWriteStream(`output\\${filepath}`);
        data.forEach((string) => {
            file.write(`${string}\n`);
        });
        file.end();
    } else {
        throw new Error(`Can't read file 'input\\${filepath}'.`);
    }
}

launch();
