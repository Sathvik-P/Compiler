import os
import sys
import itertools
from collections import defaultdict
from antlr4 import *
from grammar.SimpleIRLexer import SimpleIRLexer
from grammar.SimpleIRParser import SimpleIRParser
from grammar.SimpleIRListener import SimpleIRListener
import logging
logging.basicConfig(level=logging.DEBUG)

class Interpreter(SimpleIRListener):
    """An interpreter for SimpleIR

Limitations
- Will not interoperate with C
- May have differences due to
  - 64-bit integers vs. python integers
  - a lack of memory protection faults in our memory model
  - No stack, only a heap for locals (the stack is the sequence of .apply() calls)

"""
    def __init__(self):
        self.L = {} # mapping from label name to program counter
        self.P = [] # list of IR state transition functions for each line of the input program
        self.name = None # name of the function, set by enterFunction
        self.params = [] # list of params, set by enterParams
        self.localvars = [] # list of localvars, set by enterLocalvars
        self.retfunc = None # function to execute the return expression, set by enterReturn
        self.functions = None  # list of all functions given to the interpreter, set by link

    def link(self, functions):
        """Link the units by giving a mapping from function name to their interpreter."""
        self.functions = functions
        
    def apply(self, actuals):
        """Execute the function"""
        logging.debug(f"running {self.name}")

        E = {} # mapping from variable to address
        M = {} # mapping from address to value
        
        # initialize local variables
        for local in self.localvars:
            address = len(M)
            M[address] = 0
            E[local] = address

        # set parameters
        for param, actual in zip(self.params, actuals):  # error when param num mismatch
            address = E[param]
            M[address] = actual

        # execute the program by applying each instruction's state transition function
        i = 0
        while i < len(self.P):
            E, M, i = self.P[i](E, M, i)

        # get the return value
        retval = self.retfunc(E, M)
        
        # print out the memory state and return value for debugging
        inverted_E = defaultdict(str, { E[k]: k for k in E })
        logging.debug("memory:\n" + "\n".join([ f"M({loc}): {M[loc]} ({inverted_E[loc]})" for loc in M ]))
        logging.debug(f"return value: {retval}")
        
        return retval
    
    def enterUnit(self, ctx:SimpleIRParser.UnitContext):
        pass

    def enterFunction(self, ctx:SimpleIRParser.FunctionContext):
        """Get the function's name"""
        self.name = ctx.NAME().getText()

    def enterLocalvars(self, ctx:SimpleIRParser.LocalvarsContext):
        """Get the list of local variables"""
        self.localvars = [ local.getText() for local in ctx.NAME() ]
    
    def enterParams(self, ctx:SimpleIRParser.ParamsContext):
        """Get the list of parameters"""
        self.params = [ param.getText() for param in ctx.NAME() ]

    def enterReturn(self, ctx:SimpleIRParser.ReturnContext):
        """Create a function to evaluate the return value"""
        def retfunc(E, M):
            if SimpleIRParser.NAME == ctx.operand.type:
                operand = M[E[ctx.operand.text]]
            elif SimpleIRParser.NUM == ctx.operand.type:
                operand = int(ctx.operand.text)
            return operand
        self.retfunc = retfunc

    def enterAssign(self, ctx:SimpleIRParser.AssignContext):
        """Assign value to a variable"""
        def assign(E, M, i):
            lhs = ctx.NAME(0).getText()
            if SimpleIRParser.NAME == ctx.operand.type:
                rhs = M[E[ctx.operand.text]]
            elif SimpleIRParser.NUM == ctx.operand.type:
                rhs = int(ctx.operand.text)
            M[E[lhs]] = rhs
            i = i + 1
            return E, M, i
        self.P.append(assign)

    def enterDeref(self, ctx:SimpleIRParser.DerefContext):
        """Derefence a variable and assign is value"""
        def deref(E, M, i):
            lhs = ctx.NAME(0).getText()
            addressvalue = M[E[ctx.NAME(1).getText()]]
            M[E[lhs]] = M[addressvalue]
            i = i + 1
            return E, M, i
        self.P.append(deref)

    def enterRef(self, ctx:SimpleIRParser.RefContext):
        """Get the address of a varaible"""
        def ref(E, M, i):
            lhs = ctx.NAME(0).getText()
            M[E[lhs]] = E[ctx.NAME(1).getText()]
            i = i + 1
            return E, M, i
        self.P.append(ref)

    def enterAssignderef(self, ctx:SimpleIRParser.AssignderefContext):
        """Assign to a dereferenced variable"""
        def assignderef(E, M, i):
            if SimpleIRParser.NAME == ctx.operand.type:
                rhs = M[E[ctx.operand.text]]
            elif SimpleIRParser.NUM == ctx.operand.type:
                rhs = int(ctx.operand.text)
            lhsvalue = M[E[ctx.NAME(0).getText()]]
            M[lhsvalue] = rhs
            i = i + 1
            return E, M, i
        self.P.append(assignderef)

    def enterOperation(self, ctx:SimpleIRParser.OperationContext):
        """Arithmetic operation"""
        def operation(E, M, i):
            if SimpleIRParser.NAME == ctx.operand1.type:
                operand1 = M[E[ctx.operand1.text]]
            elif SimpleIRParser.NUM == ctx.operand1.type:
                operand1 = int(ctx.operand1.text)

            if SimpleIRParser.NAME == ctx.operand2.type:
                operand2 = M[E[ctx.operand2.text]]
            elif SimpleIRParser.NUM == ctx.operand2.type:
                operand2 = int(ctx.operand2.text)

            if SimpleIRParser.PLUS == ctx.operator.type:
                val = operand1 + operand2
            elif SimpleIRParser.MINUS == ctx.operator.type:
                val = operand1 - operand2
            elif SimpleIRParser.STAR == ctx.operator.type:
                val = operand1 * operand2
            elif SimpleIRParser.SLASH == ctx.operator.type:
                val = operand1 / operand2
            elif SimpleIRParser.PERCENT == ctx.operator.type:
                val = operand1 % operand2

            M[E[ctx.NAME(0).getText()]] = int(val)
            i = i + 1
            return E, M, i
        self.P.append(operation)
            
    def enterCall(self, ctx:SimpleIRParser.CallContext):
        """Function call"""
        def call(E, M, i):
            call = [ name.getText() for name in ctx.NAME() ]
            varname = call[0]
            funname = call[1]
            params = call[2:]
            actuals = [ M[E[param]] for param in params ]
            M[E[varname]] = self.functions[funname].apply(actuals)
            i = i + 1
            return E, M, i
        self.P.append(call)

    def enterLabel(self, ctx:SimpleIRParser.LabelContext):
        """Create a label"""
        # labels are static, that is they are collected before running
        # the program.  Otherwise, the interpreter will not know what
        # the target of the branch is when executing.
        self.L[ctx.NAME().getText()] = len(self.P)

    def enterGoto(self, ctx:SimpleIRParser.GotoContext):
        """Unconditional goto"""
        def goto(E, M, i):
            i = self.L[ctx.NAME().getText()]
            return E, M, i
        self.P.append(goto)

    def enterIfgoto(self, ctx:SimpleIRParser.IfgotoContext):
        """Conditional goto"""
        def ifgoto(E, M, i):
            if SimpleIRParser.NAME == ctx.operand1.type:
                operand1 = M[E[ctx.operand1.text]]
            elif SimpleIRParser.NUM == ctx.operand1.type:
                operand1 = int(ctx.operand1.text)

            if SimpleIRParser.NAME == ctx.operand2.type:
                operand2 = M[E[ctx.operand2.text]]
            elif SimpleIRParser.NUM == ctx.operand2.type:
                operand2 = int(ctx.operand2.text)

            label = ctx.labelname.text
            
            if SimpleIRParser.EQ == ctx.operator.type:
                result = operand1 == operand2
            elif SimpleIRParser.NEQ == ctx.operator.type:
                result = operand1 != operand2
            elif SimpleIRParser.LT == ctx.operator.type:
                result = operand1 < operand2
            elif SimpleIRParser.LTE == ctx.operator.type:
                result = operand1 <= operand2
            elif SimpleIRParser.GT == ctx.operator.type:
                result = operand1 > operand2
            elif SimpleIRParser.GTE == ctx.operator.type:
                result = operand1 >= operand2

            if result:
                i = self.L[label]
            else:
                i = i + 1
            return E, M, i
        self.P.append(ifgoto)

class BuiltIn:

    def __init__(self, applyfunc):
        self.applyfunc = applyfunc

    def apply(self, args):
        return self.applyfunc(args)

    def link(self, functions):
        pass
        
        
def main():
    import sys
    # USAGE: interpreter.py paramtest.ir main.ir 
    # USAGE: interpreter.py < many.ir
    if len(sys.argv) > 1:
        # create a mapping from filenames to their input streams
        filepaths = sys.argv[1:]
        streams = { os.path.basename(filepath): FileStream(filepath) for filepath in filepaths }
    else:
        # create a single mapping from stdin to the input stream
        input_stream = StdinStream()
        filename = "stdin"
        streams = { filename: input_stream }

    functions = {}
    functions["print_int"] = BuiltIn(lambda args: print(args[0]))
    functions["read_int"] = BuiltIn(lambda args: int(input("")))
    for filename, input_stream in streams.items():
        # generate an interpreter for each function by running the listener
        lexer = SimpleIRLexer(input_stream)
        stream = CommonTokenStream(lexer)
        parser = SimpleIRParser(stream)
        tree = parser.unit()
        if parser.getNumberOfSyntaxErrors() > 0:
            print("syntax errors")
            exit(1)
        # print(tree.toStringTree())
        walker = ParseTreeWalker()
        interp = Interpreter()
        walker.walk(interp, tree)
        # save each function's interpreter
        functions[interp.name] = interp

    # link the functions by making the function->interpreter map available to them all
    for function in functions.values():
        function.link(functions)

    # kick off interpretation with the main function
    exitcode = functions["main"].apply([])  # error if no main available

    exit(exitcode)

if __name__ == '__main__':
    main()
