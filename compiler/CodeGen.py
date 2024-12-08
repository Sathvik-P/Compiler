import os
import sys
import math
from textwrap import indent, dedent
from antlr4 import *
from grammar.SimpleIRLexer import SimpleIRLexer
from grammar.SimpleIRParser import SimpleIRParser
from grammar.SimpleIRListener import SimpleIRListener
import logging

logging.basicConfig(level=logging.DEBUG)

# Unified CodeGen class
class CodeGen(SimpleIRListener):
    def __init__(self, filename, outfile):
        self.filename = filename
        self.outfile = outfile
        self.symtab = {}
        self.bitwidth = 8  # Consistent bitwidth used in all versions

    # Common Methods
    def enterUnit(self, ctx: SimpleIRParser.UnitContext):
        """Creates the object file sections"""
        self.outfile.write(
            f'''\t.file "{self.filename}"
\t.section .note.GNU-stack,"",@progbits
\t.text
''')
    def enterCall(self, ctx: SimpleIRParser.CallContext):
        """Function call"""
        registers = ["%rdi", "%rsi", "%rdx", "%rcx", "%r8", "%r9"]
        call = [name.getText() for name in ctx.NAME()]
        variable_name = call[0] if len(call) > 1 else None  # destination variable for return val
        function_name = call[1] # function to call
        parameters = call[2:]

        # Handle up to 6 register parameters
        for i, parameter in enumerate(parameters[:6]):
            self.outfile.write(f"\tmov\t{self.symtab[parameter]}(%rbp), {registers[i]}\n")
            # push additional parameters onto stack
        for parameter in reversed(parameters[6:]):
            self.outfile.write(f"\tpush\t{self.symtab[parameter]}(%rbp)\n")

        
        self.outfile.write(f"\tcall\t{function_name}\n")

         #clean up stack
        if len(parameters) > 6:
            self.outfile.write(f"\tadd\t${8 * (len(parameters) - 6)}, %rsp\n")

        # store return value
        if variable_name:
            self.outfile.write(f"\tmov\t%rax, {self.symtab[variable_name]}(%rbp)\n")

    def enterFunction(self, ctx: SimpleIRParser.FunctionContext):
        """Emits the label and prologue"""
        function_name = ctx.NAME().getText()
        self.outfile.write(f".globl {function_name}\n")
        self.outfile.write(f".type {function_name}, @function\n")
        self.outfile.write(f"{function_name}:\n\n")
        self.outfile.write("# Prologue\n")
        self.outfile.write("        pushq     %rbp   # save old base pointer\n")
        self.outfile.write("        movq    %rsp, %rbp  # set new base pointer\n")
        self.outfile.write("        push    %rbx    # %rbx is callee-saved\n\n")

    def exitFunction(self, ctx: SimpleIRParser.FunctionContext):
        """Emits the epilogue"""
        self.outfile.write("# Epilogue\n")
        self.outfile.write("    pop %rbx # restore rbx for the caller\n")
        self.outfile.write("    mov     %rbp, %rsp # restore old stack pointer\n")
        self.outfile.write("    pop     %rbp # restore old base pointer\n")
        self.outfile.write("    ret\n")

    def enterLocalvars(self, ctx: SimpleIRParser.LocalvarsContext):
        """Allocates space for local variables"""
        locals = [local.getText() for local in ctx.NAME()]
        offsets = map(lambda x: (x + 1) * -self.bitwidth, range(len(locals)))
        self.symtab = dict(zip(locals, offsets))
        logging.debug(self.symtab)
        stackspace = len(self.symtab.keys()) * self.bitwidth
        stackoffset = math.ceil(stackspace / 8) * 8
        stackoffset += (stackoffset + 8) % 16
        self.outfile.write(indent(dedent(f'''\
            # allocate stack space for locals
            sub\t${stackoffset}, %rsp
        '''), '\t'))

    def enterParams(self, ctx: SimpleIRParser.ParamsContext):
        """Moves input parameters to their local variables"""
        registers = ["%rdi", "%rsi", "%rdx", "%rcx", "%r8", "%r9"]
        parameters = [parameter.getText() for parameter in ctx.NAME()]
        for parameter, register in zip(parameters[:6], registers):
            self.outfile.write(f"\tmov {register}, {self.symtab[parameter]}(%rbp)\n")
        for i, parameter in enumerate(parameters[6:]):
            self.outfile.write(f"\tmov {16 + self.bitwidth * i}(%rbp), %rax\n")
            self.outfile.write(f"\tmov %rax, {self.symtab[parameter]}(%rbp)\n")

    def enterAssign(self, ctx: SimpleIRParser.AssignContext):
        """Assign value to a variable"""
        operand = (
            f"{self.symtab[ctx.operand.text]}(%rbp)"
            if ctx.operand.type == SimpleIRParser.NAME
            else f"${ctx.operand.text}"
        )
        self.outfile.write(indent(dedent(f'''\
            mov\t{operand}, %rax
            mov\t%rax, {self.symtab[ctx.NAME(0).getText()]}(%rbp)
        '''), '\t'))

    def enterOperation(self, ctx: SimpleIRParser.OperationContext):
        """Arithmetic operation"""
        operand1 = (
            f"{self.symtab[ctx.operand1.text]}(%rbp)"
            if ctx.operand1.type == SimpleIRParser.NAME
            else f"${ctx.operand1.text}"
        )
        operand2 = (
            f"{self.symtab[ctx.operand2.text]}(%rbp)"
            if ctx.operand2.type == SimpleIRParser.NAME
            else f"${ctx.operand2.text}"
        )
        self.outfile.write(f"\tmov\t{operand1}, %rax\n")
        self.outfile.write(f"\tmov\t{operand2}, %rbx\n")
        if SimpleIRParser.PLUS == ctx.operator.type:
            self.outfile.write("\tadd\t%rbx, %rax\n")
        elif SimpleIRParser.MINUS == ctx.operator.type:
            self.outfile.write("\tsub\t%rbx, %rax\n")
        elif SimpleIRParser.STAR == ctx.operator.type:
            self.outfile.write("\timul\t%rbx, %rax\n")
        elif SimpleIRParser.SLASH == ctx.operator.type:
            self.outfile.write("\tcdq\n")  
            self.outfile.write("\tidiv\t%rbx\n")  
        elif SimpleIRParser.PERCENT == ctx.operator.type:
            self.outfile.write("\tcdq\n")  
            self.outfile.write("\tidiv\t%rbx\n")
            self.outfile.write("\tmov\t%rdx, %rax\n")

        destination = f"{self.symtab[ctx.NAME(0).getText()]}(%rbp)"
        self.outfile.write(f"\tmov\t%rax, {destination}\n")


    def enterDeref(self, ctx: SimpleIRParser.DerefContext):
        """Dereference a variable"""
        destination, source = [name.getText() for name in ctx.NAME()]
        self.outfile.write(f"\tmov\t{self.symtab[source]}(%rbp), %rax\n")
        self.outfile.write(f"\tmov\t(%rax), %rbx\n")
        self.outfile.write(f"\tmov\t%rbx, {self.symtab[destination]}(%rbp)\n")

    def enterRef(self, ctx: SimpleIRParser.RefContext):
        """Get the address of a variable"""
        destination, source = [name.getText() for name in ctx.NAME()]
        self.outfile.write("\tmov\t%rbp, %rax\n")
        self.outfile.write(f"\tadd\t${self.symtab[source]}, %rax\n")
        self.outfile.write(f"\tmov\t%rax, {self.symtab[destination]}(%rbp)\n")

    def enterAssignderef(self, ctx: SimpleIRParser.AssignderefContext):
        """Assign to a dereferenced variable"""
        destination = ctx.NAME(0).getText()
        operand = (
            f"{self.symtab[ctx.operand.text]}(%rbp)"
            if ctx.operand.type == SimpleIRParser.NAME
            else f"${ctx.operand.text}"
        )
        self.outfile.write(f"\tmov\t{self.symtab[destination]}(%rbp), %rax\n")
        self.outfile.write(f"\tmov\t{operand}, %rbx\n")
        self.outfile.write(f"\tmov\t%rbx, (%rax)\n")

    def enterLabel(self, ctx: SimpleIRParser.LabelContext):
        """Create a label"""
        self.outfile.write(f"{ctx.NAME()}:\n")

    def enterGoto(self, ctx: SimpleIRParser.GotoContext):
        """Unconditional goto"""
        self.outfile.write(f"\tjmp\t{ctx.NAME()}\n")

    def enterIfgoto(self, ctx: SimpleIRParser.IfgotoContext):
        """Conditional goto"""
        operand1 = (
            f"{self.symtab[ctx.operand1.text]}(%rbp)"
            if ctx.operand1.type == SimpleIRParser.NAME
            else f"${ctx.operand1.text}"
        )
        operand2 = (
            f"{self.symtab[ctx.operand2.text]}(%rbp)"
            if ctx.operand2.type == SimpleIRParser.NAME
            else f"${ctx.operand2.text}"
        )
        self.outfile.write(f"\tmov\t{operand1}, %rax\n")
        self.outfile.write(f"\tcmp\t{operand2}, %rax\n")
        jump_map = {
            SimpleIRParser.EQ: "je",
            SimpleIRParser.NEQ: "jne",
            SimpleIRParser.LT: "jl",
            SimpleIRParser.LTE: "jle",
            SimpleIRParser.GT: "jg",
            SimpleIRParser.GTE: "jge",
        }
        self.outfile.write(f"\t{jump_map[ctx.operator.type]}\t{ctx.labelname.text}\n")

    def enterReturn(self, ctx: SimpleIRParser.ReturnContext):
        """Set the return value"""
        operand = (
            f"{self.symtab[ctx.operand.text]}(%rbp)"
            if ctx.operand.type == SimpleIRParser.NAME
            else f"${ctx.operand.text}"
        )
        self.outfile.write(f"\tmov\t{operand}, %rax\n")


def main():
    if len(sys.argv) > 1:
        filepath = sys.argv[1]
        input_stream = FileStream(filepath)
        filename = os.path.basename(filepath)
    else:
        input_stream = StdinStream()
        filename = "stdin"

    lexer = SimpleIRLexer(input_stream)
    stream = CommonTokenStream(lexer)
    parser = SimpleIRParser(stream)
    tree = parser.unit()
    if parser.getNumberOfSyntaxErrors() > 0:
        print("syntax errors")
        exit(1)
    walker = ParseTreeWalker()
    walker.walk(CodeGen(filename, sys.stdout), tree)


if __name__ == '__main__':
    main()
