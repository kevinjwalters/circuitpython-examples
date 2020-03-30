
all: PlotSource-class-diagram.png Plotter-class-diagram.png


# this leaves a classes.dot lingering
PlotSource-class-diagram.png: ../plot_source.py
	pyreverse --filter-mode=ALL $<
	dot -Tpng -o $@ classes.dot
	rm classes.dot  ### would be nice to rename this and keep it

# this leaves a classes.dot lingering
Plotter-class-diagram.png: ../plotter.py
	pyreverse --filter-mode=ALL $<
	dot -Tpng -o $@ classes.dot
	rm classes.dot  ### would be nice to rename this and keep it

