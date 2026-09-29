#import <AppKit/AppKit.h>

int main(int argc, const char *argv[]) {
    @autoreleasepool {
        if (argc != 2) return 2;
        NSData *input = [[NSFileHandle fileHandleWithStandardInput] readDataToEndOfFile];
        NSBitmapImageRep *source = [NSBitmapImageRep imageRepWithData:input];
        if (!source) return 3;
        NSSize imageSize = NSMakeSize(source.pixelsWide, source.pixelsHigh);

        NSString *label = [NSString stringWithUTF8String:argv[1]];
        NSArray<NSString *> *parts = [label componentsSeparatedByString:@" "];
        if (parts.count < 4) return 5;
        NSString *heading = [NSString stringWithFormat:@"Snapshot · %@", parts[2]];
        NSString *clock = parts.lastObject;
        NSFont *font = [NSFont monospacedDigitSystemFontOfSize:54 weight:NSFontWeightMedium];
        NSDictionary *attributes = @{
            NSFontAttributeName: font,
            NSForegroundColorAttributeName: NSColor.whiteColor,
        };
        NSDictionary *headingAttributes = @{
            NSFontAttributeName: [NSFont systemFontOfSize:32 weight:NSFontWeightMedium],
            NSForegroundColorAttributeName: NSColor.whiteColor,
        };
        NSSize textSize = [clock sizeWithAttributes:attributes];
        NSSize headingSize = [heading sizeWithAttributes:headingAttributes];
        CGFloat hPad = 22, vPad = 12;
        CGFloat width = MAX(textSize.width, headingSize.width) + hPad * 2;
        CGFloat height = textSize.height + headingSize.height + vPad * 2;
        NSRect badge = NSMakeRect(
            (imageSize.width - width) / 2,
            imageSize.height - height - 28,
            width,
            height
        );

        NSBitmapImageRep *output = [[NSBitmapImageRep alloc]
            initWithBitmapDataPlanes:NULL
            pixelsWide:source.pixelsWide
            pixelsHigh:source.pixelsHigh
            bitsPerSample:8
            samplesPerPixel:4
            hasAlpha:YES
            isPlanar:NO
            colorSpaceName:NSCalibratedRGBColorSpace
            bytesPerRow:0
            bitsPerPixel:0];
        NSGraphicsContext *context = [NSGraphicsContext graphicsContextWithBitmapImageRep:output];
        [NSGraphicsContext saveGraphicsState];
        [NSGraphicsContext setCurrentContext:context];
        [source drawInRect:NSMakeRect(0, 0, imageSize.width, imageSize.height)];
        [[NSColor colorWithWhite:0 alpha:0.42] setFill];
        [[NSBezierPath bezierPathWithRoundedRect:badge xRadius:10 yRadius:10] fill];
        [clock drawAtPoint:NSMakePoint(NSMidX(badge) - textSize.width / 2, NSMinY(badge) + vPad)
            withAttributes:attributes];
        [heading drawAtPoint:NSMakePoint(NSMidX(badge) - headingSize.width / 2,
            NSMinY(badge) + vPad + textSize.height) withAttributes:headingAttributes];
        [context flushGraphics];
        [NSGraphicsContext restoreGraphicsState];

        NSData *jpeg = [output representationUsingType:NSBitmapImageFileTypeJPEG
            properties:@{NSImageCompressionFactor: @0.90}];
        if (!jpeg) return 4;
        [[NSFileHandle fileHandleWithStandardOutput] writeData:jpeg];
    }
    return 0;
}
