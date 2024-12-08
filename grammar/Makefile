GRAMMAR = SimpleIR
ANTLR = antlr-4.13.1-complete.jar

all: $(GRAMMAR)Parser.py

$(GRAMMAR)Parser.py: $(GRAMMAR).g4 $(ANTLR)
	CLASSPATH=$(ANTLR):$(CLASSPATH) java org.antlr.v4.Tool -Dlanguage=Python3 $<

$(ANTLR):
	wget https://www.antlr.org/download/$(ANTLR)

clean:
	rm -f $(GRAMMAR).interp $(GRAMMAR)Lexer.interp $(GRAMMAR)Lexer.py $(GRAMMAR)Lexer.tokens $(GRAMMAR)Listener.py $(GRAMMAR)Parser.py $(GRAMMAR)Visitor.py $(GRAMMAR).tokens

clobber: clean
	rm -f $(ANTLR)
