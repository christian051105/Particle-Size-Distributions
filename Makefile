PACKAGER=pyinstaller
SPEC=psdfit.spec
SOURCE=$(shell python -c "import pathlib; print(*[str(p) for p in pathlib.Path('psdfit').rglob('*') if p.suffix in ('.py', '.png')])")

dist\psdfit: $(SPEC) $(SOURCE)
	@if [ -d "dist\psdfit" ]; then make clean; fi
	$(PACKAGER) $(SPEC)

.PHONY : clean
clean: 
	rm -r dist\psdfit
