# Custom Compiler for SimpleIR

This project is a **compiler** that translates code written in a custom intermediate representation (**SimpleIR**) into **x86-64 assembly** and produces executable binaries. The final executable is created by linking the generated assembly with a runtime library.

## Features

- Parses a custom intermediate representation (IR) using ANTLR.
- Outputs x86-64 assembly code.
- Supports:
  - Variable assignment
  - Arithmetic operations (`+`, `-`, `*`, `/`, `%`)
  - Function calls with up to 6 parameters (register-passed) or more (stack-passed)
  - Labels and conditional jumps
- Provides a basic runtime library (`iolib.c`) for I/O operations like `print_int`.

## Requirements

1. **Languages and Tools**:
   - Python 3.x
   - ANTLR 4 (for generating the lexer/parser)
   - GCC (to compile the generated assembly)
2. **Dependencies**:
   - Python packages: `antlr4-python3-runtime`
     ```bash
     pip install antlr4-python3-runtime
     ```

## Setup

1. **Clone the Repository**:
   ```bash
   git clone https://github.com/yourusername/your-repo-name.git
   cd your-repo-name
   ```

2. **Generate Lexer and Parser**:
   If you modify `SimpleIR.g4`, regenerate the lexer and parser:
   ```bash
   java -jar antlr-4.13.1-complete.jar -Dlanguage=Python3 grammar/SimpleIR.g4
   ```

3. **Ensure GCC is Installed**:
   Verify that `gcc` is available on your system:
   ```bash
   gcc --version
   ```

4. **Check Runtime Library**:
   Ensure `iolib.c` is in the root directory.

5. **Setup Development Environment**:
   Run:
   ```bash
   pipenv install -e ./
   pipenv shell
   ```

6. **Run Initial Commands**
    Run:
    ```bash
    make -C grammar/
    ```


## Usage

1. **Write Your SimpleIR Code**:
   Create a `.ir` file, for example:
   ```ir
   function main
   localvars a b result retval
   a := 1 + 2
   b := a * 3
   result := b - 4
   retval := call print_int result
   return 0
   ```

2. **Run the Compiler**:
   Compile the `.ir` file into assembly and link it to create an executable:
   ```bash
   python3 CodeGen.py yourfile.ir > main.s
   gcc -o main main.s iolib.c
   ```

3. **Run the Executable**:
   ```bash
   ./main
   ```

4. **Expected Output**:
   For the provided `.ir` file, the output should be:
   ```
   5
   ```